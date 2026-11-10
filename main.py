import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import mercadopago
from supabase import create_client, Client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MERCADOPAGO_TOKEN = "APP_USR-1258272463364619-111017-4cecbcb6acc14e2944d6e74b1b3e68c9-573965975"
SUPABASE_URL = "https://nzarerckumoybrrcqngs.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "sb_secret_gTop5LPPWMdEzUvtCQqVeQ_XVBXu4rG"

sdk = mercadopago.SDK(MERCADOPAGO_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

@app.get("/")
def home():
    return {"status": "API ANIMUS rodando!"}

@app.post("/gerar-pix")
async def gerar_pix(request: Request):
    data = await request.json()
    valor = float(data.get("valor", 0))
    nome = data.get("nome", "Doador Anonymo").strip() or "Doador Anonymo"
    mensagem = data.get("mensagem", "")

    if valor < 1.0:
        raise HTTPException(status_code=400, detail="O valor minimo e R$ 1,00")

    payment_data = {
        "transaction_amount": valor,
        "description": f"Doacao ANIMUS - {nome}",
        "payment_method_id": "pix",
        "payer": {
            "email": "doacao@animussenadorpompeu.org",
            "first_name": nome[:30]
        },
        "metadata": {
            "doador_nome": nome,
            "mensagem": mensagem
        }
    }

    result = sdk.payment().create(payment_data)
    response = result.get("response", {})
    
    point_of_interaction = response.get("point_of_interaction", {})
    transaction_data = point_of_interaction.get("transaction_data", {})

    qr_code = transaction_data.get("qr_code", "")
    qr_code_base64 = transaction_data.get("qr_code_base64", "")

    if not qr_code:
        raise HTTPException(status_code=400, detail="Erro ao gerar PIX no Mercado Pago")

    return {
        "payment_id": response.get("id"),
        "qr_code": qr_code,
        "qr_code_base64": qr_code_base64
    }

@app.post("/webhook-pix")
async def webhook_pix(request: Request):
    try:
        data = await request.json()
        
        # Pega o ID do pagamento de qualquer formato que o Mercado Pago enviar
        payment_id = None
        if "data" in data and "id" in data["data"]:
            payment_id = data["data"]["id"]
        elif "id" in data:
            payment_id = data["id"]
        elif "resource" in data:
            resource = str(data["resource"])
            payment_id = resource.split("/")[-1] if "/" in resource else resource

        if payment_id:
            res = sdk.payment().get(payment_id)
            payment_info = res.get("response", {})

            if payment_info.get("status") == "approved":
                metadata = payment_info.get("metadata", {})
                doador_nome = metadata.get("doador_nome", "Doador Anônimo")
                mensagem = metadata.get("mensagem", "")
                valor = payment_info.get("transaction_amount")

                # Salva no Supabase (se ja existir, atualiza)
                supabase.table("doacoes").upsert({
                    "payment_id": str(payment_id),
                    "doador_nome": doador_nome,
                    "valor": valor,
                    "mensagem": mensagem
                }, on_conflict="payment_id").execute()
                
    except Exception as e:
        print("Erro no webhook:", e)

    return {"status": "ok"}
