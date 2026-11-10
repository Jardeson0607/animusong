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

MERCADOPAGO_TOKEN = "APP_USR-6901357183597422-111017-43b9d18b869c100375a585562176371d-3834462098"
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
    nome = data.get("nome", "Doador Anônimo")
    mensagem = data.get("mensagem", "")

    if valor <= 0:
        raise HTTPException(status_code=400, detail="Valor inválido")

    payment_data = {
        "transaction_amount": valor,
        "description": f"Doação ANIMUS - {nome}",
        "payment_method_id": "pix",
        "payer": {
            "email": "doacao@animussenadorpompeu.org",
            "first_name": nome
        },
        "metadata": {
            "doador_nome": nome,
            "mensagem": mensagem
        }
    }

    result = sdk.payment().create(payment_data)
    response = result.get("response", {})
    
    if "point_of_interaction" not in response:
        raise HTTPException(status_code=400, detail="Erro ao gerar PIX no Mercado Pago")

    pix_data = response["point_of_interaction"]["transaction_data"]

    return {
        "payment_id": response["id"],
        "qr_code": pix_data["qr_code"],
        "qr_code_base64": pix_data["qr_code_base64"]
    }

@app.post("/webhook-pix")
async def webhook_pix(request: Request):
    data = await request.json()
    
    action = data.get("action")
    type_event = data.get("type")
    
    if type_event == "payment" or action in ["payment.created", "payment.updated"]:
        payment_id = data.get("data", {}).get("id")
        if payment_id:
            res = sdk.payment().get(payment_id)
            payment_info = res.get("response", {})

            if payment_info.get("status") == "approved":
                metadata = payment_info.get("metadata", {})
                doador_nome = metadata.get("doador_nome", "Doador Anônimo")
                mensagem = metadata.get("mensagem", "")
                valor = payment_info.get("transaction_amount")

                try:
                    supabase.table("doacoes").insert({
                        "payment_id": str(payment_id),
                        "doador_nome": doador_nome,
                        "valor": valor,
                        "mensagem": mensagem
                    }).execute()
                except Exception as e:
                    print("Doação já existente ou erro ao inserir:", e)

    return {"status": "ok"}
