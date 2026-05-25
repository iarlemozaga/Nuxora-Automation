from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from services.auth_service import create_token
from services.discord_oauth import exchange_code

router = APIRouter(prefix="/auth")


@router.get("/discord/login")
def discord_login():
    return RedirectResponse(
        "https://discord.com/oauth2/authorize"
        "?client_id=SEU_CLIENT_ID"
        "&response_type=code"
        "&redirect_uri=https://panel.nuxora.com/auth/callback"
        "&scope=identify%20email%20guilds"
    )


@router.get("/discord/callback")
async def discord_callback(code: str):
    data = await exchange_code(code)

    access_token = data["access_token"]

    return {"access_token": access_token}
