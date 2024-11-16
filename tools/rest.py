import fastapi
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from udprpcfire import main
from functools import partial
from starlette.responses import RedirectResponse
from icecream import ic

app = fastapi.FastAPI()


origins = [
    "http://localhost",
    "http://localhost:9000",
    "http://localhost:8000",
    "https://sampadbm.github.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


CURRENT_PWM = 0
setpwm = partial(main, host="piconsys", method="setpwm")
setpwm(params=[CURRENT_PWM])


@app.get("/updown")
def npix(request: Request):
    global CURRENT_PWM
    params = request.query_params
    key = ic(params.get("key"))
    if key == "i":
        diffval = 1000
    elif key == "d":
        diffval = -1000
    else:
        return

    CURRENT_PWM += diffval

    CURRENT_PWM = min(65000, CURRENT_PWM)
    CURRENT_PWM = max(0, CURRENT_PWM)

    return setpwm(params=[CURRENT_PWM])
