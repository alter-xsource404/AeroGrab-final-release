#!/usr/bin/env python3
"""
AeroGrab - a free, open-source download manager (MIT License)

Features: multi-connection segmented downloads with dynamic splitting, pause/resume
(even after restart), queue, speed limiter, scheduler, HLS (.m3u8) video downloads,
browser extension integration, categories with auto-sorting, system tray, HTTP/HTTPS/FTP, HTTP and SOCKS5
proxies, site logins, checksum verification, automatic retry, sound alerts, dark mode, GUI (tkinter) and CLI.
Standard library only (optional: `cryptography` for AES-encrypted HLS, `pystray`+`pillow` for the tray icon,
`ffmpeg` for mp4 muxing and HLS/DASH merging - found via AEROGRAB_FFMPEG, next to this file, `imageio-ffmpeg`, or PATH; `yt-dlp` for YouTube/Facebook/Instagram/... pages).

GUI:  python aerograb.py
CLI:  python aerograb.py URL [URL ...] [-n 8] [-o ~/Downloads]
"""
import os, sys, json, time, threading, argparse, subprocess, platform, secrets, re, shutil
import http.client
import http.server, html.parser, math, copy, queue, io, base64, shlex, struct
import urllib.error, mimetypes, fnmatch, tempfile, random
import hashlib, socket, ftplib, functools, ipaddress, http.client, email.utils, glob
try:
    import ssl
except ImportError:  # a Python without TLS can still do plain http / ftp
    ssl = None
from collections import deque
from aerograb_theme import (DEFAULT_ACCENT, ACCENTS, SKINS, PAL, valid_hex, mix, luminance, contrast_fg, contrast_ratio, skin_names, make_palette,
                            set_palette, Theme, enable_dpi_awareness, style_titlebar)
import urllib.request, urllib.parse
from email.message import Message

__version__ = "1.8.3"
APP_NAME = "AeroGrab"
APP_TAGLINE = "The Download Manager You Need"
APP_NAME_VER = f"{APP_NAME} v{__version__}"   # name + version, shown in the window title and the header
APP_TITLE = f"{APP_NAME_VER} - {APP_TAGLINE}"   # window title + header text
UA = f"Mozilla/5.0 (compatible; AeroGrab/{__version__})"
CHUNK = 64 * 1024
MAIN_QUEUE = "Main download queue"
MIN_SPLIT = 1024 * 1024  # only steal work when >= 1 MiB remains in a segment
CFG_DIR = os.environ.get("AEROGRAB_HOME") or os.path.join(os.path.expanduser("~"), ".aerograb")  # AEROGRAB_HOME: keep settings elsewhere (portable install, tests)
if not os.environ.get("AEROGRAB_HOME"):  # one-time carry-over of settings + download list from the old OpenDM data folder
    _old = os.path.join(os.path.expanduser("~"), "." + "open" + "dm")
    if os.path.isdir(_old) and not os.path.exists(CFG_DIR):
        try:
            os.replace(_old, CFG_DIR)
        except OSError:
            pass
DB_FILE = os.path.join(CFG_DIR, "downloads.json")
API_PORT = 6800
# --- window icon (regenerate with tools/make_icons.py) ---
ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHLAAAz4klEQVR42uW9eZAk93Xf+Xm/zKyzzzkxB+YEBsBAJA4SBCiCBC+Q"
    "IAWJNq3RkqYdDq1lSXTYu1rtOryxijAWsd4N2dywtNYGLeqwDlo8BIsyJJAgQYLggLgIAiRAEjO4McAAg8EMZnp6uruOPH5v/8is"
    "qqysrLO7CdjbExk9XZWVlfl71/cdv/eEN8ePrPG5sk73qWt0zmrOf8MW/o38flnn99eL4PpmZwLzBhHdwC0m+X+/w6SOQe+Zwe+9"
    "zeScP+LR97OT3MuAZ70lfc5/axrgFsMNCaMdPqJwm30DOH49NcAa3+chww0H4/s9jIVbdT3vQ9aV6IdvDfPe3bbtVysr89US5893"
    "Vtr6ufeiGna/Pg3YUFgech4AVch9fZwVchVWel8Wt5soU8nvle7Xe85rvW4KnddnZijS9E8f+exKLrFvuMVNmMG+yRngFgNHBG6L"
    "2s+2/3+6yJHoHSpcg8gBVbsLZE6giiqIDpc/yZPJNxQ79V9KGXL/Pc8oIIIqdUEXEfOyCk+hPOqoffjss793tHOl3vV9kzDALQmW"
    "iDl0+tLfPOBE9hcR+zGUK8UUCoiAWlCLosAYzKyTgmtZI0aRyT4j450vGJDkUEWtHynyhBHusMpti8/8P4/lrfcbzAA3uHA4BJi+"
    "6J9f54j8BsLHxBRLaIjaEFSjNkVEZeTv1kklXddXytePERQV7ayVOCIuGAeNmhYxX7dWf/f8s//+mx3TkG9mfxoMIHCLwK129uJP"
    "70O9fy0in0Rc1DZBNUxYWjrfMwZhVN8EBF/DJZSJQh0aqwIsIq6YQswj1n4NCX5r8ZnPPpamwyR370yu8g8rHNaZ/f/sn4m4Xxbj"
    "vV3VV2xoERFEnA7x15rwbzb7PwYzjMcIMUAQiVW+RhEaIcY7gPLfl+bf4TYXHr4XDls45MAR/SlogEMO3BbN7vr0PEX3c2IKhzRq"
    "gtoQEXdiYq0H4dcK4uobyQiSdz8RgiNOGWv9e0wQ/vK5Y599MW2O1ykQFBN/et+vXUzRvVdM4ZCG9RCsTkx81RGIP6IrnA2xrKVg"
    "j3XdEe53pOfucy3BiT3femDEfZ+67gPTF/36dXA45IZb3HWSkZj4Uxf92kFHCneLmAs0CgIEb/2kXt/wMNbaaAhZR22goRjPVbSG"
    "9X9u8bnPfWcccDjiN99i4FY7s/8fXyRSuVdEtqkNYpWvkxBf8z229v91uC8tDL7GaplFB6zYwPhEn3tq/y357418k5JzPxohjgNS"
    "s9r84NJzf/BgS2DXgAFin3N297EZ3KkHxDiXaeSvwt7rgFN1DSVd1kZLrCbwpGMsu6yCCRJcIMZxFH2NILxu8cXPHWsJ7uowwKHL"
    "BW616pb/WJzCZRo1JyS+DiB+H5s5ri1PQHN8rJGJaNv+1LVHdv36nar5WlBHxTu5a+WoDUMRdyuu+RL8qsehI0Nv1hlq94/cGs3s"
    "+/VPG7f0v2jYCBDxJiP+GFI/0hpLL0DrJyUy4dHvPnPP0QkZod+jTcQEBhsF4pZ3FeaCYvO+z9/Fob90OHLbOLoorfr/d53f/093"
    "WjgKlOPAdfYzkxJ/UnU/KLImw+2qjLuuOnp0ctTIpY5o20e64VxOtSKOUbXXLD73Hx4dhAf6m4BDRwRErUb/t5hCFbXaCeoMO9r3"
    "0Q5mDT4vSQpJzus9kqQDVH+f13okdoDI97ws3Sg977X2e5rzep9npd+zamfNNLWGXeelD5tdU4mTbEZQ+3ux0B4cVwMkwZ79n36b"
    "II+ohjbOUIwp+TpEBMZR8wPdJsmXGOn8PbkTkH0O7Q8O89zaUbSCDiHHSNogq5g1EqfooP7fOffc527n0F863PZL0Wga4FD7Gv8r"
    "4oC2UncDODYr+crgc3ukgNEkvksa05Lf+X8ciRYESU6RDEAcfsTXILmGJNegAwLTGqLrfjKUlWH6P70WNn+NdZQ1z2qZmIKq9n8D"
    "4LYndEQNELsOs7s+vQ/XHgX1us9db8nvY8clqxG6/y89miHn3BxGajNHe7G17a+rajcja0c9a8+zaq9WyEr/MJdyzTWBWhHPhBpd"
    "v/z85+7PwwK9GiAp31In+oQ4hQJqo27iTyr5Ns2ZfSRC8iVe6JY6UpKOpIg4gmQbB3FdQLBhhF9r0Dy/jL9Uw1+qEdR9wqaPv1zD"
    "+g00amDDOjZooDaILaFxOlqm3/3lmi4djA/a7/ex++NqAsUiDgb9RzFtD44SelIBYXbvrzwcZ/jCqOMu6gSSryMg8KzUZ2x6Rs12"
    "pF0yZkF6JT4j6VHTJ2oGeFNlSvMzzO29kOkdW6hu3YTxPEpzMxjXoXl+iRcfOEP9XARaJ1w6TbB0iuD8CdRGGLeYrxU0DxP00w59"
    "1lRHCRqNpAUs4hi14Ylqw1z86qt/UMvEMnF71b/Y2V2/slfhSrVhSkvo6GHdLIeL5Dy0dEu9Zoip3SpdUhBde5xr6WaODCOIY4ia"
    "AZEfMrtnOzt/9ioufNdVVLZsojhTwrgdWmkE4kBQg1efPoWZihATOz828vHPHWflxQdpnH4aMW5SvWN71kT7rUl2DbRf3DjNQJIT"
    "irYDAgztaxk0tCLu9qWyXgXcD4dM2gy4Per/MFaF68QUXLXNZDlGLH3P86FzgxqSrxYlh8OzEi8p4qfAn/RIf2ImjMFfqTG1bSuX"
    "/eKH2HXDNRSnC0QB2AD8lahLalXBKxtOHVmi/voibtlBA22vZ3HDHkob9lI78TjnnrwTjXzE8cBGGW2vHRzRwhg9VWqa+lvyQbAO"
    "yJsMpYuAqsU4YsLGe4D7ueGgcLhzVn7q0Oi1CXfqYMA2gPiio7t2eSpcWtAuB+nnvZ++TnKOiOAv19j9/ndy9a8dojRfIVhWGoth"
    "r2fQugMbE/rcSw0Qg4gkyikmkAYNFKjsuBK3uomzj/8lUXMpZoIuTRCfL2ks2NJ0kpb+EZiAlIbMZYJh5kAFwzuApDS/HwhM3lT0"
    "UrDJCltGC/6MESBKB3wkxztoEbe1taLLzUuDLwGT+Z0QTYwhbDS57NBHeOe/+Ec4xTLNcyGqihjTbWrS3qkRmssRiycaGBdspElM"
    "JvmNoAhRcxlvZjsbrvokTmk6sR0m4yZKW4NJXiWk9FmTUdZSBwWDUq+LNaoRKBfFq9nfC5Bk0waiskPV0s12q5V+6XVlJOPP00H2"
    "LWLSKis0HeK332steFI1JWIQI4jrEtQaXPLxm7jyn/wC/lKIDWxM+EFrasG4wtLJBo3FAHHoROSyhxisX8OtbmH+8o8jxk1uxST3"
    "anq8kq5YQq65GwT8Ji6Dk0SYt27Y8Kmp7BeYHp217eYK2Hk0AlXJXwDb+1qa67pezwYytK/9EskzDy0/P1nAnkWNCZ9288JGwNy+"
    "XVz2SzfRPB+hyXtD5UpjdXzuxRoa2uHWTwzq1yjM76a66zps2ARjWlGJHoyailhk3kjFILpcvgwDiu0NFQ+iSfo9dFrnzNwgBgBg"
    "WnaXNd5SM3piQ0Z1adJKRbri8p1FS0uOSQhvUtog/i0khG8XHjuJRogx6+Wf+HnckosN4xtMtiQMPBAhqFvOvbSCcUDtCB8Swfo1"
    "qjvejje9DY1CECdmzNT9du49hV3y0W9m7SQ/rCxjJNjUglIKokI1CfX2ZwAxDe2Ewxgh+TAspJu1+Xn2PhNWbUs3fYI5Wdsfq37j"
    "uoT1OtuuvYILrrkMfzlCjGk/zWDpj9X/yutNamd9xJXBQpVaJbUR4pUpb78yxgJGMs9Axtz1Oiy9HtEI4d6xDguE2i8XMGKuZJBL"
    "0udFIRfhd1y8TKFF2l6SsfMmpQ2So2X3MQa1iletctmhj6KhomgSzh1+qLWIEc69tELUtAkvjgjGRLBhk9KGi3DK822MQPIMIn2e"
    "scuDyQmIyQgBoYlK8joXzEkGnR/jwUdI8Y4k+d2p1h6ELynCp8CgpJG/4+DXGuz7yHuZ27OFoB7GCzyygyJEgWXxpVqsqe1ojNNW"
    "A1GAKc5Q3HQx2KDjafSA1+4U9WBNMCh1nFpjHccLyyj8nroWG8gYVQyjMZr0IrteyTdtF67jAfSCPMjRAsYh8gPm9uzgoo++B78W"
    "R+9GVpAK4gqNhYDl1xpJZFAZ6wII2JDSpksRt5QoONPzbG3N1k8T9F2zyZLZ3T+254L5gSBN+5qjhn3pTepofphXcgsz0uCoE8hJ"
    "q01pL2bmdTFopFzy8Y/gVYv4ywHimJH3n6oqnuNw7vgKfi3EKztJ/cuYyx76uNWteLM78ReOIY6HWE0tY+f5NbNhStJRt54cQjuq"
    "NyLN+22K9ceoCOqbtRpF6DUnTk83kSWDBSTPZ+6YAsnggZYmMI5DUG+w9arL2XbN5fjLYcffH0Ng1CqLL63EmQZdxYFQ2nRZl2bL"
    "jzpmi1clJwwgQwi6enq5wy+g45mAvMCGZASe7kxfL/FNKtgjnT2m0u0eYuIwhVsuccnfvQm1OtGGYnEMzaWQpRN1jCOx9E9i8UTQ"
    "yKcwuwu3vJGoca7DrO3AcIfY2jIdrZh/6r9tmnftQ2hpUx2REMPPM0NSw0z8I70xbcmEdGlX65Av+a2/Tcrda0mUEcRxCGoN9nzg"
    "eub2bSWoxcBvLKG1YBxh+WQdf8nHOIwBqnKAsQ0Rp0Rx40XEGzmdDiP303JdyS4Z7B6uSd+pU/3jAHGrlSxyHCUfkEGvPRHg3lKq"
    "7rBudoF63SfJaInID5nasZV9H04Bv3FpZmPbu/DCEjaybRusEx5x0CmgMLcfKZQ76fBBDJ7Zx9ALClM4QBgjFsAwLyDfBKiSX9I0"
    "TOJVurWPtJ5fuut+4pqTRCV2cvjaFRVs/W0yf3fsvw18Lv6FD1GYKXWA37iKyghBPeL8yyuII1hrB6dAhsmdxC6hU5rHm9lF88zT"
    "iFNICkZMKo+vqVxhus5B+9aQ5BeYDPqxGcXe6wWMEAgat+9ATiAoi/rzAgCDJCQT/zcmBn6b33op2695Swz8JEH9Yxxx8YdQO1Wj"
    "sdDEuJKTt5jADCSuYXH+QGwC+mEdpDdNmAoMSRZXjc2XOhStDQGBdjS7k8qXt4sf0iHPdAi0K7xLl6sn/bJnGQZRFKdY4OKfvzFW"
    "4cNS4gPcP3Eczr/cIPIjPNdN1PjqfzTy8aYuwK1sJqidjvtlECUYpfU82m4SFevDVAGJZmP+GfMqk2qBXg2wDpus0wTNCfv1oP1U"
    "5A/TsfetgoB0YigBfhe+553M7d9O0IiLOybz2ISwGfL6Uy9hXAe1NpX7X80RF+KIeBTnL0ry8qnEVSrM3esidv82JnZ1kYk3uw6s"
    "Fun1AnpA4DiFHqnwZarXUZd2k+wunFTSJDcpRPt9cQQbBFS3bmLfh99DWI/aqH9sTR1Z3LLDiYd/xGs/vAfjtYRuLTRA/NzW+ngz"
    "u3EK00CSJCJdF0B3ZVP60R2DcQxBo0l9cSlmKCO9WmBsOgEsy+BAkAVGDYVKTvpSE6DXEwCQTO4/Dfo6EtIVLk2BQBLkv/+jH6Q4"
    "WyEKolRF0eiHqsW4hvrrSzx/53fBLuOfPx5veh4pBTjiEUUYbwpvehfYKI5nZIButnrIOA7GGPxag9q5JbZespcr/u77cFyPoOF3"
    "aibGcQZaTN8cNRSMTQgwSj1Axva32bi7Y4NkAV/ftEG3dmhbEGMIaw02HjzA9ndcEaN+Mb0FuSMoRI0UU3J49o57qJ9dwK0WaS4+"
    "h1fZnirgXCPLaCOKs/vxF57JeEjSFhgRgzEQBRH1pTgaeeHVl/G2X/owe669gurmAscffZ6//p//LSuvn8Px3LhWgdVrLHfVpj7H"
    "9veEOTOZMOkXBUzbP7qrgVUV8Tz2f/SDXfmX8cGZxasUOPXjZznx/cfwKuVYWJvn8FdepjC9B7X+mkEjtQFOZRNuZSvByglEnKQV"
    "IBjHQdUSNhoEtTql6TJXfOz9XPK+a7jwbT9DoSr4K8ryKZ/d79jHB//lP+av/of/C6fgjhnw69uORN3+pSij9HTOIv/sxaSnCKrb"
    "GnQzimSKJtoM4xj85Tq733898xdfiL/sY5JCj/H9fkNQ83n2jm+1PYpWrMJffB6vsmNtcbEqGENhbj/ByiuIMYiBKAjwa3U0Ctm4"
    "+wIuv/Gd7HvnlWy5ZDso+DVLfTHCcQzGc6gtWHZeeZCZbRupnVnEKXiphNXkHdbctXvSDLAjZ9NkppRbpDcO0FXynbxmg5DK5g3s"
    "ufG93cBvbGm0eFMFnrn925w/foLC9BQaJUWy4hL55whaWiBapRaQtMnxKUzvoFmaw18+S9AMqMxW2X3FAS6+/mr2vfMKqhuKBD7U"
    "F0OMSUCg6ZSQqYVCuURppsLSqddx8npzrdIEJPtJIxG1oKZ/+rElvaqZqF9LbefEAQbaD8kPeqjGRZ5+g70f+gCl+alY+ieI+KlV"
    "nKLHuRde5aXvPhSr/iizmUMc/PMvxFhgtfZVpc3TURgRRi54O5i9QDnwnndwybuvZuOuLeBAUFdq50LEEYxjeiCStRav4nDu+GkW"
    "XjqO6zmdLZvttR8lLtBKB9dluAbQUU1Kn+2FOeEsye3W0OspxJU8sc8fNhrMH7iYbddehb8yIfBrAeFIeeZv78IGAW6plAJSLffV"
    "SbTACbyp3SNhAckuSRLcUlWCZkQUWspTLjsOVNn7393MtotnKc8VCX1orgRJqVvs8uUupVXEQLEi/OCLt9NYXKQ8vzGuWBKZKFuf"
    "vn138BPqiHou68Nr/0ZNXeg+E+7tubQijmHfR25Mav7CxJeeAPhNFTh++PssPP0cXrWa2vSsXXhGxOAvPY9b3pbaldMf/iidOAUK"
    "YRARBRGuZ9i0s8ruyzew87J5ZjeXEQOhb6kvBrG0t8rGpJ8DYfEKDk5RuOO3Psv3/+zLlGZnkspjF8km3YbaxZHdwFEbNPZpmJcT"
    "X+ra3tVrATpFEalASLBSY8e738X8xbsJVvzxCz0SEGY8l9qpcxz71ndwSkVU81yolgubaIHaKxTaWiDHJdbOvUZhRBhEOI4ws6nE"
    "9ovm2HVwA5sunMIrGsLA4tfDdjCrn7R3kSqMKM54+LU6X/nNz/DEHXdR3TQbe0NriFHdwTFk7Rvm7bIDoimaSi+fZHftSl8o0D7f"
    "BiHF+Xn2fPD9hM0IJgZ+4DqG5++8G39pCa9S6W55kMP8IoZg+QW88vZuLSGdzSs2sgRBvLF0ZkOJbfs3suvgRjbunKJUdbGREoaW"
    "5kqsteKK5tHyE2qV6kaPE0+8yO3/4rd59SdHqG6aS6KBTieE3CX5MhFucXP0pYzsTkgWEEgvSOjbEzETE0hfxQhhvcn+j/0CpY0z"
    "beA3zqNJCzyVC5x6/CinHns8Bn7tXbyD2rp1awE0iEO7CdHVKuWqx9Zds+z5mY3sODBPecrDqhAGUUL0+DniyuVRY0YWt+BQqAqP"
    "feUw3/g//j2N8+eobJxBo3iPQzt/0jeBtwYaQHWQf5mtVUoXOtKuk+9JYuXxhnaix50AmSFoNJi9aD/brn07/ko4EfBTYg/CX67z"
    "wp3fRBx3rFIvY1zC2os4pW1EQYS1lsp0ge37N7Bt7yxb98wys7GMOLHdb9ZSkm7GT922VH5zqcbXbv0PPPaVOylUCxSnK1hrk06w"
    "TgLbTKqoVLsXWsfaF9ATCJKRPtY3uqS53CmS93/tZMeypkOEPR/+EOIaNAjAmDG5O67r88oOL9z5HWqnTiXAzw4NEsWSGBE0A+zK"
    "qxSnTrBt32Vs3zvFhZdsZGq+hDhCGEYEfpgojNQehQliE2KE6kaPl37wDHf8q3/Ha0efprJhGtUIRTGOm6h9t50V7U5bT+6uuiOm"
    "DQeEFbUPD2W3f2vvuZnyJjEOQa3Gtndex4YD+wlqzQT46ZiLGuGWCpx75kVOPPgwbqXcJ3Yu7QybjSxBvYZapTRVYeuevVx09VvZ"
    "fvFepjfMYtx444jfTJpwG8EYWVWsyEaWQtUDlPs+9xW++/ufJ/TrVDbFKh/TqoF0Unsi04mTPi3sVg8CxzABktXtWUCi9MZ6tbf9"
    "iwg2DCnOzrD7gzcS+pMDP8QQBREv3HlXDJxINW1JRSBtFBHUfVQtxXKZ3QcvYffPHOSCvbuY2bwRxxOiQGNJD8CIIM7q+xC3pL4y"
    "53Hy6eN86zN/wLP3PUR5tkphqhI3/3adxN47STFJVuVbVlW9vW6h4O7UXp94QW+oWIwhrNfY+3M3U948j7/cnAz4RZbCVJGX7rmP"
    "xWPH2qq/3SQqDAl9H1DK1So7LrqU3QcvY8vuC5nbujluChFaQj8g9FNAbi1mrGoMTItTcRz/u3/4Nzzwx58nqK8wtXkuBqgCxvE6"
    "Ui8GUcm0pdNJOS9ZdH9IJFBH4KaeGIrmINJ0GxTthI6zewtFiBoNZvbuYdt11xFMGPFTVRzPY/nEaV6+5zBuudSWfr/ZRKOIqfk5"
    "tl52Cdv27WP7/n3MbNqYEF0Jmj40NQXkZM18bhtZXM+hXPV45YljfPeP7uDYI0dxHaE0W4k1leO0t7qJmCSJLmRrDbv6LmhqPWFs"
    "BnHXXvpzKoOz7/VsfIhLqXZ/6KMYzyOsN9uAbNzEG0Z48a5vETWb4BiatRqFUonte/ex7y1vZeeBi5manwGBKLTrSvRWKBeB8oxH"
    "c9nn7t+7g8f/5j6sKtNbLyCsK2H9JOIWUyrfpMMrdPov6tqNQpwMA0gPiOobUetpC5sFg9op9KjX2Pr2a5m/9EAb+I1r+9XGqv/k"
    "I49x8oeP4hSLbNiwid0HL2fXJZexYds2HDfx02vN5LvXh+jpgE5pykOBp+55jAf/4uucevZlynOzOIUiOEW86d3YaDGRegdtAT3V"
    "JFWdv3ZxInuU/gw/NQwwqWoMKUxNc+GNH8X6diLgJ6qI63L+1dc5dufX2LZ3Pwfe/g72HPwZSpUiYaQEfkDotyTdDCxMWgvCe2UP"
    "twjHH3+e733xTo49+iROoUB180YQD/FKGK+CKc5hwwXC+kkwhc7eRNqtXdZ1/SfwAkZ1E7W/Rmi7fUK4UmPXjT9HZevGGPiNKP1p"
    "3ROq4lpL4eRpbrj577Ht4gM4juD7AfWVRpvoIsJ6DZpqEd4tehQrcPrYazz8l3fx1HcexVqlPD+HGA9xCphCBeNVELeCU5jFm7uE"
    "qHkmtvs6Wlc2HblDyyQMMC7de+xSehOj5OdcjCFqNJjetYdt73oPQS0BfiNJPFgUi+JaZWME0w1LZc8BxHMImk3CJJNojGE9p4u1"
    "Jb7o4ZWF86fO8dAX7uXxr95HY7lGeXYG4xXAeBi3HEt9QnzjlBDj4VV3ExSfwjbPxsjfDqFtv64xE9BvbTSAMhgD5D1N0pZl14d/"
    "HqdQIKw1R9rTryghSiFKCB8JBQQ1EIQh2BAj66Tf8yS+5FEoC0unz3P/5+/m6LcfZmVhieJ0lerGjSAuxi0hXkJ8t4K4JcQpIsYD"
    "BOOU8ab30WicTmUe+/Rl0lHKvt9sGEC1S2eLIwT1FbZcdR3zl11OUPOHAz+FCItrLZsDYTYyeIA1ECZu+nqq+C7Cq+KVCnhFWHj1"
    "LM8++EMe/+q9LL52huJUNbHzLuIWE6kvtyUeU0BMobNrGMHaELe6Gzn7eFKKliPuqqsp/WupXR2DAUbJLmV64JJJSki2XXwcpdMo"
    "xKtW2fnhX8CGtm8OoxVeiMRiIstcABtDwcO0Cb/WQ0IHeRkAXrmAKcDCKyc5+u2H+fFd93P+5OsUymWK5QpYh8g3GLeImApqK2hU"
    "BopYCjheMRn8mbpzG2LcadzKhfiLR+O5XNrPDgzqFsaQCG7rp5DbLXzMgDupTiCan+5Ln9PaJCRCUFth9wduprptK8FyI5YGzcTo"
    "UaJ4UjbTgbIxMJQ0VvU/NcKrYq0ijlCoFDAGzrz8Cj/4m6/y5OHD+DUoze3g8l/9FIW52bi5pOPGvrxxwLhJGNdgXAd/OeDUAy91"
    "r09qC743vR///NP0b8Vjc4J14/z4Q02A5iP5XKSXknTpg/6TFmwS+61xv/46Uzt3s+3dHySo+UkHT80AvPhfKVA2+sJ05LQJb34K"
    "hFdr4w2ohQKliiGK4MTRJ/nh336VYz/4Ac2VZQrVCqVpB6fgsOntV1HdMY9tatyVNDvgQcF4Qu3UMqfuP54rcxr5OKWtuKXNhLUT"
    "sZZQHQFfkcIF/WxB/+iR2yu2K6hWR8gCMiDx032jkgQ1RBUbRez80MdxiiXCWgNx4pBv6yohFieybG4K86ET76g3Y6UrJ5d2jV3T"
    "QrmIU4DlM+d56ruP8OS993Li6BEC36dYLVOem4mfTCzKCmGtgb/UxPphfo2fgvEMUT0csPs4bmLtTu0nWD4O4iSdyuKOpJoJBatm"
    "tqMP1ON9GzrmYAAxOpYG6A7rEA8Xaf3uLK44hrC2zMYrrmPDW64iqDU6wC9x6yIiZpqwpWkoqBAZiNYZ16m1qIBX8CiWDVEIJ595"
    "hqfuu5fnHn6YxddOYlyHQqWMVynG2spInKN3HDABEMSRPBP19T46ALX/Gmrk41Z3Y7xpbLCSL+25HcMZoAEGl4q5o8PJEfZitdOU"
    "JpZ4icGf4kAU4pQrXHjTLyatWKSNEyMsYiMuqBvmAgPrbOc1cUEd16FQKWIcOH/6LMfufZRnHriPE08eJWg28MolynPTHak2BmMc"
    "xHFjW28cxHhxYHbQNHiNq7iH4mqNMG4Fb2ofjTOPIFJMQQUdc+T8aHRbhRvY78KpvkLaGtkihCvLXPjRT1LduTMBfgasEhBR9pUL"
    "Gg5lG0v9ehPeLRUplIRmzefFxx/jmYfu59hjj7J85vVY2stl3MpMS3QRx8Tt4B23/Rvjxrt9Wx1ARo6Z6BCNFOJNX0Rz4UdgbYbo"
    "do1pFTNA3rCa/mojF/Arqult3bbzW1yiZp3K9l1se+/PEdaTAktVrA3Z0BA2N12MdKR+PQiPKl6piFuCsyde49nv3ccz37ufMy8d"
    "I4pCCuXYtrfVdNKFTFoSb7x4RlAL2aeaO8QNowdrgI65HsIoUYApbsQtbydYej4Z1Zzp1qKpvzVvKHe/JN6ocQCdIOxr0hzeaYJk"
    "AA1Ddt70CdxKhXCljoqgUcgFNcN84BCZYY1MVkd4t1TELQinjr3IkXvv4umH7mNl4WwczKmUKZjkoQzJ5k0HWtKeOlrS3u5bmAp1"
    "DzMBHZM92txFb+YSgvPP95Z9tQHgqAHAwVMPeuIAIo7GCQmTf+Vhmp8ODoiTPUvMv/U6Nl55HeFKgwgwYcDOFYfpyCFcp1C9tRa3"
    "4OEVHc6eeIXHv3kHTz5wD35thUK1QmV+lk5KWhJ77rYlnhbhxUkIb3rH1bXTtmNq44GxNUGtj1u5EKcwT9TOD2h3cEh1SMg+D8i3"
    "4gBlXZdQsGaKgtVGmGKJnR/5+2hoCW1IIVR2rriU1BAazW4eXzOpL02XWDpzhvu//Fcx4esrFCoVKnOzCZInRfBU4CaR9I6aT0ce"
    "uoth0y7dKHFTHeWsxJ6IW8abuZjwtfsQp8j4rWLHywVk5LofZNX+OKBNfWlLf7Bynp03fYqpXXupLy0xFcCOmotLTHyzXlJfcjh6"
    "33d48LY/Y3nhNMWpKUoz052eU2lAl0h+h+hOp4FVDtFziTkM4Wc9t6EBdkGjAHf6IuTMo9DOD6T8/94poRMxwio1QF4oOMEyzTqV"
    "rbvY9r6PU6/VmGnAjroXN0cQXXt7by2lqRLLC2f49p/+GU8/9B28UrEt8WIkcd8ccLwuuy4tomN6VXw/LdO1+ENAgCY4qT2/Z8iz"
    "iIANMIV53OoegnM/QUyxkxXU7CjZiYmXwwDLQEX7hBdzgGAmCqwam0wNfHbc9CmoVpk7vcQ2vwhmpGjC2CpfgPJUiacfeZD7vvSH"
    "LC+cojQ9E3+fgHHcuHW743aIn9j2dgv6bP5COzY5re3axE/tyY8nk4wAAkcJZ6aBoloKs5cSnHsi5WbkhYFHFPhgrTSA9vcIxHEI"
    "a8vMHbyGmauvp/r6EjsaRSJn7cO52grdlgo8dPuX+P7ffgGn4FGenYmlPgnYGKeQADsvScM6qWEOg3tkaxRiw6h3wnjKBWv1Gx6K"
    "ASyoHw1W/67pzg+Ut+OWthHWXom3hanmx3pG+BGRgW5g8qajw41afzOgNsTxPLZ+5FNMr1h2rHhE61B1oGpxXBfjGu7+09/lyH1f"
    "pzw7izjxpE9xPIxbiCU+kfo24bvU/IDQrI1wp6Zxq1PYMEjiHJmRbgmjDTXuGm95L26u9gHP8f00z660G0wIipgi3uylhCvH6Aw5"
    "Xu22sCkdEgiaIMCkxNK/ssjmDx5i0/bLuOC1Buo66xK/dwseUeTzjT/8DMd+9CCVubnEpXMQNyG6U4irbkxnk4XKEMJr2h1TxHXY"
    "9w/+Ie7UNDYI+parR2FIT/lbymZqaHFnSuz5h9fmPI/iVjxe/cZR6ifPY4puS5/GWmBqH+LNomGtF5TqWFTqec8Mha0jdwkVbNCg"
    "sHk7u999iB1nQoxx1rymVVUxrkMUBXz99/81xx6/n8rsLEhMLPEKcTGGW0wk30nNHZRURm3A4yQVucZzaLx2kmNf+gJY7dQtrOEk"
    "XY0Ut1Lg7KPHef2hFzAFpzsEbAOMN4M7fREaNemMjpl0dG/3j1mFHulWgwLWr7P9A59kv3MBThBhZTUTT/O/SwSMY7jn87/DS0cf"
    "pjI3h2IR18W4hcTep4Bey51rT4e0qdBqXgtx20brGkW45TJLzz7Fi3/1ZcQrJM2pdU3obyPFlDyWj53h1W8cwSk4uSNo1IYUZg4i"
    "phC3OF8lyQZ7AaR75o72JWIcwtoSlQNXcfDgTbjLDSLHrEtot1guc/iLn+Xph79FdX4jViOMGxOd1pFU4WhP8iWD7kdI0miSxTzz"
    "/QcpbNjI9ptuJlxebk8lWxUzuw7B+Qav3P44GlnEc9peTde1Ix9T3opTuZBg6bn2/IGxR+Pk5AJ6J4eKO/6VbYR1DW95zy+zMSjE"
    "6d01D/JElKbK/OTw1/jxd75CdXYOJUJctwP0xE31483M1M2bFN01Nzbb87/zWbURTqXCybu+yusPP4hTqWJbLebGblHeYTYROHHH"
    "j2ieXcF4JhlVmzPsMsmUeLMHJywF6/9jBsPJ4bZfjMGvLbLrbR/l4p1X4/u1yZo5DQF9hWKJUy88y4Nf+X2KlUpcZmYcjPGSBgpO"
    "OzPXReAe1T4KkbKfi8BaxPN46T//J5aefRKnXIm7dU0g+Wpj1f/a3U+y9PRJ3LKHRhboP4lMoybu1F6c0kaw/ph4LUveLdpXA4zu"
    "XnSAX2l+K2/72V9Gm35sc9cY+Ykx2Cjk8Bd/lzCsYzynE9lr+fXtQI5FkxIqbZdSpQiZZYwuQmfOSV1DNYpXK4o49hd/TPP104hX"
    "wkZ2LAVgI4tTLnDuhy9x5sFncdrEHxJKToZRuTOXoDZgvF2iOpIGGNO31Li/rr/CW6//ZeamtxBG/pond6yNKJSLPP7tv+K1F34c"
    "l14n3URoEz8j9TZFSNtiiDRT2LgULH10naPtc9IagCjEeC7BuTO88Oe/T+Q3kWTKyEjAzyqm6FE7fpaTX/8JxnPGmkeoUYA3fSni"
    "VFJgcHQEMPrgyPRI1D6HiBDUz7Nlz9VcfMXNNBu1pAR6bUGfWyhw7uQJHvvmFyhUyjHib22jTtrZtnbpYFvEt6n/R53/26jzfr/D"
    "Rqnzop5rahhgiiVWjj3DS1/6jzH4HEUTJzGFsBbxyu0/xAYhaiSJIo4whQRQ68fFItW93S7hSCPO+7uB3UNHxdFRbRlieNsNv45r"
    "XKxa1vpH1eJ6Lo/d/SUaKws4rpfE5lP5+VhNgEZtKe5PYO1mjrxDte/n21oiDHArVc49+gCv/M0XMeWpIaYgmRAmDsf+5HdonDyB"
    "KRbj7xu63Ss7jMrizV4ek27sbdSiY5iA/ocYIaydZ/7K9+FfuIuo2cAxazdwqcVgrlvg/OunOfaje/FKJSBqD45s1Rxp22YnkqsR"
    "alvMECVqPMo/0uPDco7YNCTXSq4df0fMBE6lwmvfvJ3Th7+OOzXd03w6DWKdSpVX/vrPWXj4a2jwVNy1Ve2YcZwYDDqVC3HKF4Bt"
    "jhm46x8JHNQWPMtF2NDHm93Elncf4tjZJzly+gdYjXC9Ymp78yptv1q8ksvzj93DysKruJ5Hd6NpTdn4qGOvbUqVtyTXZux/Gwek"
    "mSWDA2zGLKSuHTNF/FmnVOKV//wnLP7kUZzqNDaKuoKNNopwqjO8ft9dnLzzy7gzW/DP/YSocQJaW8DGHHUq4uHNHIzXeugmWBmI"
    "DHMmhy5IKmbaw2Eigm3W2PzeT+DObMI0m7x69gUe/NFfs7DwCsViBTFOqh/vhP6pcWjW6jz98J04nhdLqnSma2ua2C2JTR0dwrUk"
    "N+z+u0fFpyS863NRN9FTr2GjRA9Zjv3J71J/5RimVGmjeo0inFKVlRee4vgX/l9MoZAwXoC/8P32dLHxDrBRA2dqP8argg1GcP/a"
    "ZkSGmoBSaaWJUs/VLGKIGstU913J/DU/T1hfAuPieWWWG4s88Mht/OSJuwn8RswIIh1XbOxkT4HTLz7FmeNP4RVKyR4CSULLacmP"
    "cmx5SrJt1Eb5vYAw6gZ9bSyRfCZ1jawWaH9HGGIcl2hlkWN/9BnClSXE9bBRiLgewfIiL/7Rv8E26nHDyyhExCNcfo5o5VnEnUl2"
    "CxdHPEqIODjFLbizb+k0sx5qAdR3IqkPTQefPn1kubxxywI423qa0msckdr6oV9BvGK8BbpQRoolCtVZAhWeev4hjr/8E/bvv4Zd"
    "u95CuTKNYolsEAPF1j6wzFiY+NA4lYvFLQinXzqCDRuIqXaVYUkLPLXKsjUzhSTdfzbVrVxHqkjIFlp0z3DVrmqcJFYQhjjFIvXj"
    "z/HiH3+Gff/0X7VrDI//2b+j9vLzuNXpOHDUigJi8F+/L07zpl26UYRFFREHGy5ldhL3r9pRWDJmeSH++zbbhwEOOXBbhMqrInIw"
    "/ehiXMLls2y49mNMHbiGYOksplDBCX20MotGEapKxTj4K0s8/uNv8tyz32frlr1s23ExGzbtoFCq4Bbc3pnlSVGOSSbHRaFSO7/M"
    "S0/cHw9NbC1aYlw1CY22BkukB02ppgifyrN3M8Uw+mt35K6LEdIlWZ3fNoxwqlOc/9GDvPylz7L7n/wmL//FH7DwyGHc6Tk0ClLx"
    "+9iDssEiUfN0H+IPicirJruQvT7ET3OLEayeXlh4dDmL+TLJoFPJ0unTwAfadyGCDZsUNl/IBTf/cxCDU55FozBOuxYqmOIUTvkc"
    "4fIipjRFoVknqK/w/CtP8MLxJ6iUp5mbv4CZYgnXhhSnZilWptoDlG0UsHT2BMtnX+Xca8c4c+Jp/PoCbrGUTOFMNppogl1TEi1d"
    "TECKKVJmr4sRRs1y9tMImqMNFA0jnEqVs/d/g6i2zOKPHsKpVBPi2y4G0oQJxJS6R76kh1QMq9TQkWqRk2Y99jkgagv54JIw/T7w"
    "6V4HwPDybf8nGvqd+bYttysK0CjARgEahWhk44KKpHFzLQx5zVqC5XOo3+iEcVNBH41iQGMcwfEcHNdJkjvp+r9OciQmtHamjmek"
    "v7fAc9QoZWZ0d8YcdLVvy2gDVQXHYeHhb2OKJXp2jbTbvyUmJHZ5uom6qoKfno6tCkZRHkkLeR8GeK+FwzhiHog0tPHGEVHUihiH"
    "4Pxp/NePZ1wP7bLP6QXTjI4XDAXXQwpTucBQTKGdqxei7qxta4GTRWvPH2pJuybVtCkmkGwv+uxU82xZmOYxQY4JIB1daxG+m1lM"
    "qZwAxwzhs5KrmbI6VcbvBpnXn6H9ulEiMcbcm00E5bJL/OuQKW947XHEuTz2aaS9Q79nfm3qIZROAqUNkOjl6B4wlirT6owNbvXz"
    "S+r208OXs6PlyEh7v5Hs9E41yUq+jmUGshKtOVghj/h9bP6q6jykb8ZOsa+XtXDRwsK3FrNckhO8v8GFr0Veac8OEefdEEUddzHb"
    "s9bm9hWWlOSngX57K5bEt9U+EsJ36NbaeBmXc0l6xm6ObpS+QxOyEjdKB7NseNbS3bTRprRRDiDsMgsMIfxaSn7eZzUS8QTV25cW"
    "7vlCbP+P2AEmAOCwBQjhi66G/zIJvOfsHOqXPUxJZ6tSuN3elN78tGRstKRMRmr3rWh3/WG6D2H3xKI0EExdt1/f4rxn0DypTJk6"
    "HeQuarfnkPUsejZz2AG7esdJ8+Z+1ihWLPbPx4wT3mLgVluev/4bGO9GNLT52kLobQ0zoH+war6yTQ+VajGFZOYQt79RusfOZhiv"
    "exhFzkQiGX1NlT5Sm+Mq9kh8X7cus0brIvlxIRniGGx0tL5wwVtTvr8O0QAARwTAGvvbDvohHWlL8LAhE3RtrpDcGQKpczUFYluL"
    "JC0JlETtp4muvZ8XyYBRhve67qsRtK9W6N4hnMcgOWu1qpEvo3xWEUSs8G9jt+8GFw6HI2cKWlqgNHf9XWLcG9EwSswBgzOIg8bJ"
    "DPqs5CBzyUHsvWZDsoMpZAC+HYwBh1TIdTOB5mqCfuZDcrThJMUzacnve04i/fZo/VztSrg5gltzgwYD9uzcCiDW8BuORo93qg8Y"
    "fazcmBVG3b0HcxYxlQxKjx7r5Dg0pe77NLgapm0HMUFPL4A+dl374aTVz/gZ7bNxPDRS/R/h0QD2OfTpL+MM/oZDTlT/+im3tMsY"
    "470/9gjETJB6nNCrkX6FDWN9vaRG249Tj6B98wT9GWR4YGlNFmbQjYcinqs2/NPG4v2/k438jXs1gUMGbtPy/LvuEXHfoxqEyfC6"
    "Cblz3OeVwbcnjKDqZXVSNlArDHneNS3jHkr8CHEc1D5dN/p2zuyoJeCv702Y4StwW+LDBZ+yGp1MdkJGq7vR8SSxf8w7U/fWm//u"
    "jld0FVlqn3NzPpNXVaNDttCP3NJtzYhvwQhKTaz9BGceWBpFGkekVKxGyjPXvQPj3oNoPIA3nnHCumgDoQ9ql35NO4abjhxIMNB7"
    "HUWVSx9tMFqfxtUTPsn0xKcZg9q/Uz/3wO39UP8qRDW+YHH22vcacb+KSKU9x5x1YoJJMcLqJGkyU7Euk11GeT6NkjYnaBR9snH+"
    "wS+NSvwJVjC+cGn+uneh5jYjZpvGKTzvDWGCVTPDGpin9X2ooYAv3phgV1D9B/XFB//LOMQf5gXk/Lxo4QY3bNz/olPc+teCebuI"
    "u6fTw2yYh/BTItK6MISyzvObxlinODEh4jmoPYoNPlY//71vj0v8CRigxQSHnKj5rbNhY9+fu6WgBLwrnvcSRSN2wmH9VzMH6Mk4"
    "7VyH761/A6Q+rqmL+9oJGv7Huvi/FC4+8sIkxF+tmLR6wlKa/9l3Cva3wXlPYpbiSpF2DveNYoL/Wn5kmOpJauAcIxis2h8aiX6r"
    "tvC9O9Mgfb0MzShxggigPPuzf8+ivyHC9UJrBJpVIKK7qH9SZpD/Siiqq1j+tNoxYEw8TU0B+5iq/F5z0f98HOE75Azz839KC3qL"
    "SceaS3PX3YDy91X1JjFml2A6FUM6rL3p/58lvpMFjdNdFlU9CXq3Wr7gL33v67RDupNL/TpKVIYjt761WmqWrsZyPcg1oPtV2CYw"
    "BVIajBfWzJF+g4k8NCHWajroK7Is8BrwHCKPqnJ/E/dRFu9b6LvGby4GSN8k5HLo/NtmS8iMDbxq93Zl248Remed5Oxw6f+ZQt/r"
    "DFmaZIH9Pq/nfELy3ut3frpdSwFxbKNJbZHFH5/rJW57Pdd8lqysvxgcMnEl6hZdjwf4b/PnkPPTWrM3AlSNOvhL1vC9VWaDxgIr"
    "k3wmDwC+ORzPN8n3T7oFdq2eT9fhvTcFAn4zuFXyJmIYXSMivekJ3/r5/wAge21Z36K+OQAAAABJRU5ErkJggg=="
)
# --- end window icon ---
# --- header brand mark, pre-scaled so it stays sharp (regenerate with tools/make_icons.py) ---
# --- brand marks ---
BRAND_B64 = {
    32: (
        "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"
    ),
    64: (
        "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"
        "HUHcIWeSAAAAAElFTkSuQmCC"
    ),
}
# --- end brand marks ---
# --- ui icons (regenerate with tools/make_icons.py) ---
ACTIVE = ("Connecting", "Downloading")


def human(n):
    if n is None or n < 0:
        return "?"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def size_mb_bytes(n):
    """'12.34 MB (12,939,264 Bytes)': the size line of the Download complete dialog."""
    if n is None or n < 0:
        return "unknown size"
    return f"{n / 1048576:.2f} MB ({n:,} Bytes)"


_WIN_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.I)
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")  # zero-width and bidi marks: invisible, but they end up in file names
MAX_STEM = 120  # characters; leaves room for " (12)", the extension and the folder inside Windows' 260-character path limit


def clean_name(s):
    """A file name that is valid on Windows (and so everywhere): no forbidden or control characters, no reserved device names
    (CON, NUL, COM1 ...), no trailing dots or spaces, a bounded length, and the extension kept intact."""
    s = _INVISIBLE.sub("", str(s or ""))
    s = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in s).strip(" .")
    if not s:
        return "download"
    stem, ext = os.path.splitext(s)
    if len(ext) > 12 or " " in ext or not stem:
        stem, ext = s, ""
    if len(stem) > MAX_STEM:
        cut = stem[:MAX_STEM]
        sp = cut.rfind(" ")
        stem = (cut[:sp] if sp >= MAX_STEM * 0.6 else cut).rstrip(" ._-")
    if _WIN_RESERVED.match(stem):
        stem = "_" + stem
    return (stem + ext) or "download"


# ============================ checksums ============================
HASH_ALGOS = ("md5", "sha1", "sha256", "sha512")
_HASH_LEN = {32: "md5", 40: "sha1", 64: "sha256", 128: "sha512"}


def parse_checksum(text):
    """'sha256:ab12...', 'AB12... *file.iso' (sha256sum style) or a bare hex string -> ('sha256', 'ab12...'); None if it isn't a hash."""
    t = (text or "").strip()
    if not t:
        return None
    m = re.match(r"(?i)^(md5|sha-?1|sha-?256|sha-?512)\s*[:=]\s*([0-9a-f]+)\s*$", t)
    if m:
        algo, hexs = m.group(1).lower().replace("-", ""), m.group(2).lower()
    else:
        hexs, algo = t.split()[0].lower(), None
    if not re.fullmatch(r"[0-9a-f]+", hexs):
        return None
    algo = algo or _HASH_LEN.get(len(hexs))
    return (algo, hexs) if algo and _HASH_LEN.get(len(hexs)) == algo else None


def normalize_checksum(text):
    """'' for a blank value, else 'algo:hex'. Raises ValueError if the text isn't an MD5 / SHA-1 / SHA-256 / SHA-512 value."""
    if not (text or "").strip():
        return ""
    cs = parse_checksum(text)
    if not cs:
        raise ValueError("not an MD5, SHA-1, SHA-256 or SHA-512 value")
    return f"{cs[0]}:{cs[1]}"


def hash_file_multi(path, algos=HASH_ALGOS, stop=None, progress=None):
    """Read the file once and return {algo: hexdigest} ({} if `stop` was set). progress(done_bytes, total_bytes) is called as it goes."""
    hs = {a: hashlib.new(a) for a in algos}
    total, done = os.path.getsize(path), 0
    with open(path, "rb") as f:
        while True:
            if stop is not None and stop.is_set():
                return {}
            buf = f.read(1 << 20)
            if not buf:
                break
            for h in hs.values():
                h.update(buf)
            done += len(buf)
            if progress:
                progress(done, total)
    return {a: h.hexdigest() for a, h in hs.items()}


def hash_file(path, algo="sha256", stop=None, progress=None):
    return hash_file_multi(path, (algo,), stop, progress).get(algo)


# ============================ appearance: dark mode + accent colours ============================
def system_is_dark():
    """Does the operating system currently prefer dark apps? (False when it can't tell.)"""
    try:
        s = platform.system()
        if s == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if s == "Darwin":
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=2)
            return "dark" in r.stdout.lower()
        if "dark" in os.environ.get("GTK_THEME", "").lower():
            return True
        if shutil.which("gsettings"):
            for key in ("color-scheme", "gtk-theme"):
                r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key], capture_output=True, text=True, timeout=2)
                if "dark" in r.stdout.lower():
                    return True
    except Exception:
        pass
    return False


def resolve_mode(setting):
    """'light' | 'dark' | 'system' (follow the OS) -> 'light' or 'dark'."""
    return setting if setting in ("light", "dark") else ("dark" if system_is_dark() else "light")


def set_dark_titlebar(win, dark):
    """Kept for callers/tests: the title bar follows the live palette (see aerograb_theme.style_titlebar)."""
    style_titlebar(win, PAL)


# ============================ sound alerts ============================
SOUND_EVENTS = (("complete", "A download finishes"), ("all_done", "Everything in the queue is finished"),
                ("error", "A download fails (or fails its checksum)"))
SOUND_PRIORITY = ("error", "all_done", "complete")  # when several things happen at once, only the most important one is played
_WIN_SOUND = {"complete": "SystemAsterisk", "all_done": "SystemExclamation", "error": "SystemHand"}
_MAC_SOUND = {"complete": "Glass", "all_done": "Hero", "error": "Basso"}
_LINUX_SOUND = {"complete": ("complete", "bell"), "all_done": ("service-login", "message", "complete"), "error": ("dialog-error", "dialog-warning", "bell")}
_LINUX_PLAYERS = (("paplay",), ("pw-play",), ("ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"), ("play", "-q"), ("aplay", "-q"))


def sound_plan(event, system=None, custom="", which=shutil.which, exists=os.path.isfile):
    """What to run to make the sound for `event`: ('win', alias_or_wav, is_file) | ('cmd', argv) | None (nothing available)."""
    system = system or platform.system()
    f = custom if custom and exists(custom) and (system != "Windows" or custom.lower().endswith(".wav")) else ""
    if system == "Windows":
        return ("win", f or _WIN_SOUND.get(event, "SystemAsterisk"), bool(f))
    if system == "Darwin":
        f = f or f"/System/Library/Sounds/{_MAC_SOUND.get(event, 'Glass')}.aiff"
        return ("cmd", ["afplay", f]) if which("afplay") and exists(f) else None
    if not f:
        for name in _LINUX_SOUND.get(event, ("complete",)):
            for ext in (".oga", ".ogg", ".wav"):
                p = f"/usr/share/sounds/freedesktop/stereo/{name}{ext}"
                if exists(p):
                    f = p
                    break
            if f:
                break
    if not f:
        return None
    for argv in _LINUX_PLAYERS:
        if which(argv[0]) and not (argv[0] == "aplay" and not f.lower().endswith(".wav")):
            return ("cmd", [*argv, f])
    return None


def run_sound(plan):
    """Start playing (never waits for the sound to end). True if something was started."""
    if not plan:
        return False
    try:
        if plan[0] == "win":
            import winsound
            winsound.PlaySound(plan[1], (winsound.SND_FILENAME if plan[2] else winsound.SND_ALIAS) | winsound.SND_ASYNC)
        else:
            p = subprocess.Popen(plan[1], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_ff_flags())
            threading.Thread(target=p.wait, daemon=True).start()  # reap it, so no zombie processes pile up
        return True
    except Exception:
        return False


def in_hours(start, stop, now_min=None):
    """Is the clock inside start..stop ('HH:MM', overnight ranges like 22:00-07:00 work)?"""
    if now_min is None:
        t = time.localtime()
        now_min = t.tm_hour * 60 + t.tm_min
    try:
        a, b = parse_hm(start), parse_hm(stop)
    except ValueError:
        return False
    if a == b:
        return False
    return a <= now_min < b if a < b else (now_min >= a or now_min < b)


class SoundPlayer:
    """Plays at most one sound per burst of events, never while you are looking at the window (if you ask), never in quiet hours."""
    GAP = 1.5  # seconds between sounds

    def __init__(self, settings, focused=lambda: False, runner=None, clock=time.time):
        self.st, self.focused, self.clock, self.last, self.fallback = settings, focused, clock, 0.0, None
        self.runner = runner or (lambda ev, custom: run_sound(sound_plan(ev, custom=custom)))

    def allowed(self, event, now_min=None):
        st = self.st
        if not st.get("sound", True) or not st.get("sound_" + event, True):
            return False
        if st.get("sound_unfocused_only") and self.focused():
            return False
        return not (st.get("sound_quiet") and in_hours(st.get("sound_quiet_from", "22:00"), st.get("sound_quiet_to", "07:00"), now_min))

    def play(self, event, force=False):
        """Play one sound now. force=True ignores the rules (the Test buttons)."""
        custom = (self.st.get("sound_files") or {}).get(event, "")
        ok = self.runner(event, custom)
        if not ok and self.fallback:
            self.fallback()
        return ok

    def flush(self, events):
        """events: the set of things that happened since the last call. Returns the event that was played (or None)."""
        now = self.clock()
        pick = next((e for e in SOUND_PRIORITY if e in events and self.allowed(e)), None)
        if pick is None or now - self.last < self.GAP:
            return None
        self.last = now
        self.play(pick)
        return pick


def draw_segmap(cv, cells):
    """Bar showing which parts of the file are downloaded. cells = [(x0, x1, filled_to)] in 0..1."""
    cv.delete("all")
    W, H = max(cv.winfo_width(), 100), max(cv.winfo_height(), 10)
    if not cells:
        cv.create_text(6, H / 2, text="Select a single download to see its segments", anchor="w",
                       fill=PAL["muted"], font=("TkDefaultFont", 8))
        return
    for x0, x1, xf in cells:
        cv.create_rectangle(x0 * W, 1, x1 * W, H - 1, fill=PAL["seg_empty"], outline=PAL["seg_border"])
        if xf > x0:
            cv.create_rectangle(x0 * W, 1, xf * W, H - 1, fill=PAL["accent"], outline="")



# ============================ categories & auto-sorting ============================
def _cat(name, exts="", folder="", sites=""):
    return {"name": name, "exts": exts.split(), "folder": folder, "sites": sites.split()}


DEFAULT_CATEGORIES = [
    _cat("General"),  # catch-all: saved straight into the download folder
    _cat("Compressed", "zip rar 7z tar gz tgz bz2 xz zst lz lzma cab z"),
    _cat("Documents", "pdf doc docx xls xlsx ppt pptx odt ods odp txt rtf csv epub mobi md odf pages"),
    _cat("Music", "mp3 flac wav aac m4a ogg opus wma aiff mka weba amr mid midi"),
    _cat("Video", "mp4 mkv avi mov webm flv wmv m4v ts mpg mpeg 3gp m2ts vob ogv mts rm rmvb asf"),
    _cat("Images", "jpg jpeg png gif webp bmp svg tif tiff ico heic avif"),
    _cat("Programs", "exe msi dmg pkg deb rpm apk appimage iso bat sh msix msp appx jar whl"),
]


def classify(cats, name, url=""):
    """Category for a file: a website rule wins, then the file extension, else General."""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    for c in cats:
        if any(host == s or host.endswith("." + s) for s in c.get("sites", []) if s):
            return c["name"]
    ext = os.path.splitext(name or "")[1].lower().lstrip(".")
    if ext:
        for c in cats:
            if ext in c.get("exts", []):
                return c["name"]
    return "General"


def category_folder(cats, name, base):
    """Where a category's files go: its own folder (absolute, or relative to `base`), else <base>/<name>."""
    c = next((c for c in cats if c["name"] == name), None)
    f = os.path.expanduser((c or {}).get("folder") or "")
    if f:
        return f if os.path.isabs(f) else os.path.join(base, f)
    return base if c is None or name == "General" else os.path.join(base, clean_name(name))


def matches_filter(d, flt):
    kind, _, val = flt.partition(":")
    if kind == "unfinished":
        return d.status != "Completed"
    if kind == "finished":
        return d.status == "Completed"
    if kind == "cat":
        return d.category == val
    if kind == "queue":
        return d.queue == val and d.status != "Completed"
    if kind == "queues":
        return d.status != "Completed"
    if kind == "project":
        return d.project == val
    if kind == "projects":
        return bool(d.project)
    return True


def unique_path(folder, name):
    stem, ext = os.path.splitext(name)
    path, n = os.path.join(folder, name), 0
    while os.path.exists(path):
        n += 1
        path = os.path.join(folder, f"{stem} ({n}){ext}")
    return path



# ============================ list-view formatting (IDM style) ============================
def fmt_left(sec):
    """Time left, IDM style: '12 sec', '2 min 15 sec', '1 h 03 min'."""
    if sec is None or sec < 0:
        return ""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min {s:02d} sec" if m else f"{s} sec"


def fmt_rate(bps):
    if not bps or bps < 1:
        return ""
    n, i = float(bps), 0
    while n >= 1024 and i < 3:
        n /= 1024
        i += 1
    return (f"{n:.0f}" if i == 0 else f"{n:.1f}") + f" {('Bytes', 'KBytes', 'MBytes', 'GBytes')[i]}/sec"


def fmt_when(ts):
    return time.strftime("%b %d %H:%M:%S %Y", time.localtime(ts)) if ts else ""


def status_text(d):
    if d.status == "Completed":
        if getattr(d, "scan", "") == "infected":
            return "Complete - THREAT FOUND"
        if getattr(d, "_verifying", False):
            return "Complete (checking hash...)"
        if getattr(d, "_scanning", False):
            return "Complete (scanning...)"
        return {"ok": "Complete (hash OK)", "bad": "Complete - HASH MISMATCH", "missing": "Complete (file missing)"}.get(getattr(d, "verified", ""), "Complete")
    if d.status == "Error":
        wait = getattr(d, "retry_at", 0) - time.time() if getattr(d, "retry_at", 0) else None
        again = "" if wait is None else (f"retry in {int(wait) + 1}s: " if wait > 0 else "waiting for network: ")
        return "Error" + (f": {again}{d.error[:40]}" if d.error else (f": {again}" if again else ""))
    note = f" ({d.note[:30]})" if getattr(d, "note", "") else ""
    if d.status == "Connecting":
        return "Connecting..."
    if d.status == "Downloading":
        return (f"{d.percent:.2f}%" if d.size > 0 else "Receiving...") + note
    if d.status == "Queued":
        return "Queued"
    return (f"Stopped {d.percent:.1f}%" if d.size > 0 and d.done else "Stopped") + note


def queue_positions(items):
    """Q column: each unfinished download's place (1, 2, 3...) in its queue."""
    count, out = {}, {}
    for d in items:
        if d.status != "Completed":
            count[d.queue] = count.get(d.queue, 0) + 1
            out[id(d)] = count[d.queue]
    return out


COLUMNS = (("name", "File Name", 230), ("q", "Q", 34), ("size", "Size", 70), ("status", "Status", 108),
           ("left", "Time left", 96), ("rate", "Transfer rate", 120), ("last", "Last Try", 162), ("desc", "Description", 80))


def sort_key(d, col, qpos):
    if col == "name":
        return d.label.lower()
    if col == "q":
        return qpos.get(id(d), 10 ** 9)
    if col == "size":
        return d.size
    if col == "status":
        return (d.status == "Completed", d.percent)
    if col == "left":
        return d.eta_sec if d.eta_sec is not None else float("inf")
    if col == "rate":
        return d.speed
    if col == "last":
        return d.last_try
    return (d.desc or "").lower()


# ============================ site grabber (find downloadable files on a web page) ============================
PAGE_EXTS = {"", "html", "htm", "php", "asp", "aspx", "jsp", "shtml", "xhtml"}
NOISE_EXTS = {"css", "js", "json", "xml", "map", "woff", "woff2", "ttf", "otf", "eot", "rss", "atom", "ico"}


class _LinkParser(html.parser.HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.links, self.title, self._in_title = base, [], "", False

    def _add(self, tag, value):
        value = (value or "").strip()
        if value and not value.lower().startswith(("javascript:", "mailto:", "data:", "tel:", "#", "blob:")):
            u = urllib.parse.urldefrag(urllib.parse.urljoin(self.base, value))[0]
            if u.lower().startswith(("http://", "https://")):
                self.links.append((tag, u))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._in_title = self._in_title or tag == "title"
        for k in ("href", "src", "data-src", "data-original", "poster"):
            self._add(tag, a.get(k))
        for part in (a.get("srcset") or "").split(","):
            self._add(tag, part.strip().split(" ")[0])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def extract_links(html_text, base):
    """All absolute http(s) links on a page as [(tag, url)], plus the page title."""
    p = _LinkParser(base)
    try:
        p.feed(html_text)
    except Exception:
        pass
    return p.links, " ".join(p.title.split())


def url_ext(u):
    return os.path.splitext(urllib.parse.urlparse(u).path)[1].lower().lstrip(".")


def default_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.5"})
    with OPENER.open(req, timeout=20) as r:
        if "html" not in (r.headers.get("Content-Type") or "text/html").lower():
            return "", r.geturl()
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read(2 << 20).decode(charset, "replace"), r.geturl()


def grab_site(start, wanted, depth=0, any_file=False, max_pages=20, fetch=default_fetch):
    """Look for downloadable files on a page (and, with depth=1, on pages of the same site it links to).
    wanted: set of extensions; any_file: also accept any other file-looking link.
    Returns (files, title) where files = [{"url", "name", "ext", "page"}]."""
    host = urllib.parse.urlparse(start).netloc
    todo, seen, files, found, title = [start], {start}, [], set(), ""
    while todo and len(seen) <= max_pages:
        page = todo.pop(0)
        try:
            text, final = fetch(page)
        except Exception:
            continue
        links, t = extract_links(text, final)
        title = title or t
        for tag, u in links:
            ext = url_ext(u)
            if ext in wanted or (any_file and ext and ext not in PAGE_EXTS and ext not in NOISE_EXTS):
                if u not in found:
                    found.add(u)
                    name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(u).path)) or urllib.parse.urlparse(u).netloc
                    files.append({"url": u, "name": name, "ext": ext, "page": page})
            elif depth > 0 and tag == "a" and ext in PAGE_EXTS and urllib.parse.urlparse(u).netloc == host and u not in seen and len(seen) < max_pages:
                seen.add(u)
                todo.append(u)
    return files, title


def tray_tooltip(items, speed):
    active = sum(d.status in ACTIVE for d in items)
    queued = sum(d.status == "Queued" for d in items)
    if not active and not queued:
        return "AeroGrab - idle"
    return f"AeroGrab - {active} downloading, {human(speed)}/s" + (f", {queued} queued" if queued else "")


class _Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            for k in [k for k in new.headers if k.lower() in ("cookie", "authorization")]:
                del new.headers[k]  # a login or cookie is only ever sent to the host it was meant for
        return new


# ============================ network: proxies, logins, FTP, retry rules ============================
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
URL_SCHEMES = ("http://", "https://", "ftp://", "ftps://")  # what the Add dialog, the CLI and list import accept (the browser API stays http(s) only)
RETRY_DELAYS = (15, 30, 60, 120, 300, 600)  # seconds before automatic retry no. 1, 2, 3 ...
PROXY_KEYS = ("proxy_mode", "proxy_type", "proxy_host", "proxy_port", "proxy_user", "proxy_pass", "proxy_bypass")


def _host_of(url):
    return (urllib.parse.urlsplit(url if "//" in url else "//" + url).hostname or "").lower()


def split_login(url):
    """'ftp://me:pw@host/x' -> ('ftp://host/x', ('me', 'pw')); a link without credentials -> (url, None)."""
    p = urllib.parse.urlsplit(url)
    if "@" not in p.netloc:
        return url, None
    info, _, host = p.netloc.rpartition("@")
    user, _, pw = info.partition(":")
    return urllib.parse.urlunsplit((p.scheme, host, p.path, p.query, p.fragment)), (urllib.parse.unquote(user), urllib.parse.unquote(pw))


def parse_bypass(text):
    return list(LOCAL_HOSTS) + [x for x in re.split(r"[,;\s]+", text or "") if x]


def bypass_match(host, patterns):
    """Should `host` skip the proxy? Patterns: example.com / .example.com / *.example.com (the domain and its sub-domains), 10.0.0.0/8, an address, *."""
    host = (host or "").lower().strip("[]")
    for p in patterns:
        p = p.strip().lower()
        if not p:
            continue
        if p == "*":
            return True
        if "/" in p:
            try:
                if ipaddress.ip_address(host) in ipaddress.ip_network(p, strict=False):
                    return True
            except ValueError:
                pass
            continue
        p = p[1:] if p.startswith("*.") else p
        p = p[1:] if p.startswith(".") else p
        if host == p or host.endswith("." + p):
            return True
    return False


def proxy_port(st):
    try:
        port = int(st.get("proxy_port") or 0)
    except (TypeError, ValueError):
        port = 0
    return port or (1080 if st.get("proxy_type") == "socks5" else 8080)


def proxy_url(st):
    """The manual proxy as one URL (http://user:pw@host:port or socks5h://...), '' if no manual proxy is set. Also what yt-dlp is given."""
    if st.get("proxy_mode") != "manual" or not st.get("proxy_host"):
        return ""
    auth = ""
    if st.get("proxy_user"):
        auth = urllib.parse.quote(st["proxy_user"], safe="") + (":" + urllib.parse.quote(st.get("proxy_pass") or "", safe="") if st.get("proxy_pass") else "") + "@"
    host = st["proxy_host"].strip()
    host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"{'socks5h' if st.get('proxy_type') == 'socks5' else 'http'}://{auth}{host}:{proxy_port(st)}"


def parse_proxy(text):
    """'http://user:pw@host:3128' or 'socks5://host:1080' -> the proxy_* settings. Raises ValueError for anything else."""
    p = urllib.parse.urlsplit(text if "//" in text else "http://" + text)
    if p.scheme not in ("http", "https", "socks5", "socks5h") or not p.hostname:
        raise ValueError("a proxy looks like http://host:port or socks5://host:port")
    return {"proxy_mode": "manual", "proxy_type": "socks5" if p.scheme.startswith("socks") else "http", "proxy_host": p.hostname,
            "proxy_port": p.port or 0, "proxy_user": urllib.parse.unquote(p.username or ""), "proxy_pass": urllib.parse.unquote(p.password or "")}


class SocksError(ConnectionError):
    pass


class SocksAuthError(OSError):
    pass


_SOCKS_REPLY = {1: "general failure", 2: "not allowed by the proxy's rules", 3: "network unreachable", 4: "host unreachable",
                5: "connection refused", 6: "TTL expired", 7: "command not supported", 8: "address type not supported"}


def _recv_n(s, n):
    buf = b""
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            raise SocksError("the SOCKS proxy closed the connection")
        buf += c
    return buf


def socks5_connect(proxy, dest, user="", password="", timeout=30):
    """Open a TCP connection to dest=(host, port) through a SOCKS5 proxy (RFC 1928, user/password login per RFC 1929). Names are resolved by the proxy."""
    s = socket.create_connection(proxy, timeout=timeout)
    try:
        methods = b"\x00\x02" if user else b"\x00"
        s.sendall(b"\x05" + bytes([len(methods)]) + methods)
        ver, method = _recv_n(s, 2)
        if ver != 5:
            raise SocksError("that is not a SOCKS5 proxy")
        if method == 2:
            u, p = user.encode(), (password or "").encode()
            if len(u) > 255 or len(p) > 255:
                raise SocksAuthError("the proxy user name or password is too long")
            s.sendall(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            if _recv_n(s, 2)[1] != 0:
                raise SocksAuthError("the SOCKS proxy refused the user name or password")
        elif method == 0xFF:
            raise SocksAuthError("the SOCKS proxy needs a user name and password")
        elif method != 0:
            raise SocksAuthError("the SOCKS proxy wants a login method AeroGrab doesn't support")
        host, port = dest
        try:
            addr = b"\x01" + socket.inet_pton(socket.AF_INET, host)
        except OSError:
            try:
                addr = b"\x04" + socket.inet_pton(socket.AF_INET6, host.strip("[]"))
            except OSError:
                h = host.encode("idna")
                addr = b"\x03" + bytes([len(h)]) + h
        s.sendall(b"\x05\x01\x00" + addr + struct.pack(">H", port))
        _, rep, _, atyp = _recv_n(s, 4)
        if rep != 0:
            raise SocksError(f"the SOCKS proxy could not connect: {_SOCKS_REPLY.get(rep, rep)}")
        _recv_n(s, ({1: 4, 4: 16}.get(atyp) or _recv_n(s, 1)[0]) + 2)
        return s
    except BaseException:
        s.close()
        raise


def _socks_open(cfg, host, port, timeout):
    t = timeout if isinstance(timeout, (int, float)) else 30
    return socks5_connect((cfg["host"], cfg["port"]), (host, port), cfg.get("user", ""), cfg.get("pass", ""), t)


class _SocksHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *a, cfg=None, **k):
        super().__init__(*a, **k)
        self._cfg = cfg

    def connect(self):
        self.sock = _socks_open(self._cfg, self.host, self.port, self.timeout)


class _SocksHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *a, cfg=None, **k):
        super().__init__(*a, **k)
        self._cfg = cfg

    def connect(self):
        sock = _socks_open(self._cfg, self.host, self.port, self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _SocksHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, cfg, bypass):
        super().__init__()
        self.cfg, self.bypass = cfg, bypass

    def http_open(self, req):
        direct = bypass_match(_host_of(req.full_url), self.bypass)
        return self.do_open(http.client.HTTPConnection if direct else functools.partial(_SocksHTTPConnection, cfg=self.cfg), req)


if ssl:
    class _SocksHTTPSHandler(urllib.request.HTTPSHandler):
        def __init__(self, cfg, bypass):
            super().__init__()
            self.cfg, self.bypass = cfg, bypass

        def https_open(self, req):
            direct = bypass_match(_host_of(req.full_url), self.bypass)
            return self.do_open(http.client.HTTPSConnection if direct else functools.partial(_SocksHTTPSConnection, cfg=self.cfg), req, context=self._context)
else:
    _SocksHTTPSHandler = None


class _Proxy(urllib.request.ProxyHandler):
    """Manual HTTP proxy: like ProxyHandler, but with our own 'don't use it for these hosts' list."""

    def __init__(self, proxies, bypass):
        super().__init__(proxies)
        self.bypass = bypass

    def proxy_open(self, req, proxy, type):
        if bypass_match(_host_of(req.full_url), self.bypass):
            return None
        return super().proxy_open(req, proxy, type)


class _Logins(urllib.request.HTTPPasswordMgrWithDefaultRealm):
    """Which user name / password to give a server that asks for one (HTTP Basic or Digest): looked up by host name."""

    def __init__(self):
        super().__init__()
        self.by_host = {}

    def find_user_password(self, realm, authuri):
        u = authuri[0] if isinstance(authuri, (list, tuple)) else authuri
        return self.by_host.get(_host_of(u), (None, None))


def _clamp_int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


class Net:
    """Every connection AeroGrab makes goes through here, so the proxy and the site logins can be changed while it runs."""

    def __init__(self):
        self.cfg, self.proxy_url, self.logins = {}, "", _Logins()
        self.configure({})

    def configure(self, st):
        st = st or {}
        self.cfg = {k: st.get(k) for k in PROXY_KEYS}
        # Configuration > Connection / Save to / Downloads
        self.timeout, self.retries = _clamp_int(st.get("timeout"), 5, 300, 30), _clamp_int(st.get("retries"), 0, 30, 6)
        self.temp_folder, self.overwrite = str(st.get("temp_folder") or "").strip(), st.get("file_exists") == "overwrite"
        self.logins = _Logins()
        mode, bypass, handlers = st.get("proxy_mode") or "system", parse_bypass(st.get("proxy_bypass")), [_Redirect()]
        self.proxy_url = ""
        if mode == "none":
            handlers.append(urllib.request.ProxyHandler({}))
        elif mode == "manual" and st.get("proxy_host"):
            self.proxy_url = proxy_url(st)
            if st.get("proxy_type") == "socks5":
                cfg = {"host": st["proxy_host"].strip(), "port": proxy_port(st), "user": st.get("proxy_user") or "", "pass": st.get("proxy_pass") or ""}
                handlers += [urllib.request.ProxyHandler({}), _SocksHTTPHandler(cfg, bypass)] + ([_SocksHTTPSHandler(cfg, bypass)] if _SocksHTTPSHandler else [])
            else:
                handlers.append(_Proxy({"http": self.proxy_url, "https": self.proxy_url}, bypass))
        handlers += [urllib.request.HTTPBasicAuthHandler(self.logins), urllib.request.HTTPDigestAuthHandler(self.logins)]
        self._opener = urllib.request.build_opener(*handlers)  # no proxy handler of our own = urllib's default: the system / environment proxy
        for x in st.get("site_logins") or []:
            if isinstance(x, dict) and x.get("host"):
                self.add_login(x["host"], x.get("user", ""), x.get("pass", ""))

    def add_login(self, host, user, password):
        self.logins.by_host[_host_of(host)] = (user, password)

    def login_for(self, url):
        v = self.logins.by_host.get(_host_of(url))
        return v if v and v != (None, None) else None

    def open(self, req, timeout=None):
        return self._opener.open(req, timeout=timeout)

    def ffmpeg_proxy_args(self):
        """ffmpeg only knows HTTP proxies (not SOCKS)."""
        return ["-http_proxy", self.proxy_url] if self.proxy_url.startswith("http://") else []


OPENER = Net()
NET = OPENER  # live network / save settings (timeout, retries, temp folder, overwrite) next to the proxy and logins


# ============================ Configuration: browser capture rules, click / typing sounds, start with the computer ============================
def parts_dir(path):
    """Where the pieces of a segmented (HLS) download are kept: next to the file, or in the temp folder from Configuration > Save to."""
    if OPENER.temp_folder:
        return os.path.join(OPENER.temp_folder, os.path.basename(path) + ".parts")
    return path + ".parts"



# ---- which browser downloads does AeroGrab take over? (Configuration > File types; the extension reads the same rules) ----
DEFAULT_SKIP_TYPES = "jpg jpeg png gif webp bmp svg ico avif heic tif tiff css js mjs map html htm json xml woff woff2 ttf otf"
BROWSER_NAMES = (("chrome", "Google Chrome"), ("edge", "Microsoft Edge"), ("brave", "Brave Browser"), ("firefox", "Mozilla Firefox"), ("other", "Other Chromium browsers (Opera, Vivaldi ...)"))
KEY_CHOICES = ("none", "alt", "ctrl", "shift")


def split_list(text):
    return [x.strip().lower().lstrip(".*") for x in re.split(r"[\s,;]+", str(text or "")) if x.strip().lstrip(".*")]


def site_excluded(host, sites_text):
    h = (host or "").lower()
    for p in re.split(r"[\s,;]+", str(sites_text or "").lower()):
        p = p.strip()
        if p and (fnmatch.fnmatch(h, p) or h == p.lstrip("*.") or h.endswith("." + p.lstrip("*."))):
            return True
    return False


def capture_decision(st, url, filename="", forced=False):
    """Should AeroGrab take this link over from the browser? Same rules as the extension: excluded site -> no; skip list (images, web assets) -> no;
    capture list -> yes; anything else -> the 'unknown types' switch."""
    p = urllib.parse.urlsplit(url or "")
    if p.scheme not in ("http", "https"):
        return False
    if not forced and site_excluded(p.hostname, st.get("exclude_sites")):
        return False
    if forced:
        return True
    ext = os.path.splitext(filename or "")[1].lstrip(".").lower() or url_ext(url)
    if ext in split_list(st.get("skip_types")):
        return False
    if ext in split_list(st.get("capture_types")):
        return True
    return bool(st.get("capture_unknown", True))


def browser_config(st):
    """What the browser extension needs to know (served on /config and by the native host)."""
    br = st.get("capture_browsers") if isinstance(st.get("capture_browsers"), dict) else {}
    key = lambda k, d: st.get(k) if st.get(k) in KEY_CHOICES else d
    return {"intercept": bool(st.get("capture_downloads", True)), "capture_types": split_list(st.get("capture_types")),
            "skip_types": split_list(st.get("skip_types")), "capture_unknown": bool(st.get("capture_unknown", True)),
            "exclude_sites": split_list(st.get("exclude_sites")), "min_size_kb": _clamp_int(st.get("min_size_kb"), 0, 10 ** 9, 0),
            "key_prevent": key("key_prevent", "alt"), "key_force": key("key_force", "none"),
            "browsers": {k: bool(br.get(k, True)) for k, _ in BROWSER_NAMES},
 "ctx_link": bool(st.get("ctx_link", True)), "ctx_media": bool(st.get("ctx_media", True)), "video_button": bool(st.get("video_button", True))}


# ---- start with the computer ----
def set_autostart(enabled, cmd=None, home=None):
    """Start AeroGrab (minimized) when the user signs in. Returns '' or an error text."""
    cmd = cmd or launch_command()
    try:
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as k:
                if enabled:
                    winreg.SetValueEx(k, "AeroGrab", 0, winreg.REG_SZ, subprocess.list2cmdline(cmd))
                else:
                    try:
                        winreg.DeleteValue(k, "AeroGrab")
                    except FileNotFoundError:
                        pass
            return ""
        home = home or os.path.expanduser("~")
        if platform.system() == "Darwin":
            path = os.path.join(home, "Library", "LaunchAgents", "org.aerograb.plist")
            body = ('<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict><key>Label</key><string>org.aerograb</string>'
                    "<key>ProgramArguments</key><array>" + "".join(f"<string>{html_escape(c)}</string>" for c in cmd) + "</array>"
                    "<key>RunAtLoad</key><true/></dict></plist>\n")
        else:
            path = os.path.join(home, ".config", "autostart", "aerograb.desktop")
            body = "[Desktop Entry]\nType=Application\nName=AeroGrab\nComment=Download manager\nExec=" + " ".join(shlex.quote(c) for c in cmd) + "\nTerminal=false\n"
        if enabled:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
        elif os.path.exists(path):
            os.remove(path)
        return ""
    except Exception as e:
        return str(e)


def html_escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def check_proxy(st, url="http://example.com/", timeout=10):
    """(ok, message): can a request get out through the proxy described by settings `st`?"""
    n = Net()
    n.configure(st)
    try:
        with n.open(urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA}), timeout=timeout) as r:
            return True, f"Works - the proxy answered (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        if e.code == 407:
            return False, "The proxy wants a (correct) user name and password"
        return True, f"The proxy answered (HTTP {e.code})"
    except Exception as e:
        return False, str(getattr(e, "reason", None) or e)


def is_transient(e):
    """Is this failure worth trying again later (network trouble, a busy server) rather than a refusal that won't change?"""
    if isinstance(e, urllib.error.HTTPError):
        return e.code in (408, 425, 429) or e.code >= 500
    why = getattr(e, "reason", e)  # urllib wraps the real error in a URLError
    if isinstance(why, SocksAuthError) or (ssl and isinstance(why, ssl.SSLCertVerificationError)):
        return False  # a wrong proxy password / a bad certificate won't fix itself
    return isinstance(e, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ftplib.error_temp, EOFError)) or bool(ssl and isinstance(e, ssl.SSLError))


def retry_after(e, cap=120):
    """Seconds the server asked us to wait (Retry-After header, seconds or a date); 0 if it didn't."""
    h = getattr(e, "headers", None)
    v = (h.get("Retry-After") if h is not None else "") or ""
    v = v.strip()
    if v.isdigit():
        return min(int(v), cap)
    try:
        return max(0, min(cap, int(email.utils.parsedate_to_datetime(v).timestamp() - time.time())))
    except (TypeError, ValueError, IndexError):
        return 0


def default_net_check():
    """True if the internet (or the configured proxy) can be reached at all - so retries aren't wasted while the network is down."""
    cfg = OPENER.cfg
    if cfg.get("proxy_mode") == "manual" and cfg.get("proxy_host"):
        targets = [(cfg["proxy_host"].strip(), proxy_port(cfg))]
    else:
        targets = [("1.1.1.1", 443), ("8.8.8.8", 53), ("9.9.9.9", 443)]
        for v in urllib.request.getproxies().values():  # behind a company proxy the outside world isn't reachable directly
            p = urllib.parse.urlsplit(v if "//" in v else "//" + v)
            if p.hostname:
                targets.insert(0, (p.hostname, p.port or 80))
    for t in targets:
        try:
            socket.create_connection(t, timeout=2.5).close()
            return True
        except OSError:
            continue
    return False


class Limiter:
    """Smooth bandwidth limiter shared by every connection that uses it (bytes/s, 0 = off)."""
    def __init__(self, rate=0):
        self.rate, self.next, self.lock = rate, 0.0, threading.Lock()

    def set_rate(self, rate):
        with self.lock:
            self.rate, self.next = max(0, int(rate)), 0.0

    def wait(self, n, stop=None):
        with self.lock:
            if self.rate <= 0:
                return
            now = time.monotonic()
            start = max(self.next, now)
            self.next = start + n / self.rate  # reserve this chunk's time slot
            delay = start - now
        if delay > 0:
            stop.wait(delay) if stop is not None else time.sleep(delay)


GLOBAL_LIMIT = Limiter()


def _chunk_for(*limiters):
    """Smaller reads under a tight limit keep the speed smooth and pausing responsive."""
    rates = [l.rate for l in limiters if l.rate > 0]
    return CHUNK if not rates else max(2048, min(CHUNK, int(min(rates) // 8)))


def power_off():
    try:
        sysname = platform.system()
        if sysname == "Windows":
            subprocess.Popen(["shutdown", "/s", "/t", "5"])
        elif sysname == "Darwin":
            subprocess.Popen(["osascript", "-e", 'tell application "System Events" to shut down'])
        else:
            subprocess.Popen(["systemctl", "poweroff"])
    except OSError:
        pass


def parse_hm(text):
    t = time.strptime(text.strip(), "%H:%M")
    return t.tm_hour * 60 + t.tm_min


# ============================ universal engine helpers ============================
def find_ffmpeg():
    """ffmpeg to use: $AEROGRAB_FFMPEG, a copy bundled with AeroGrab (next to the program, in ./ffmpeg or ./bin, inside a
    PyInstaller build, or in ~/.aerograb), the imageio-ffmpeg package, else whatever is on PATH."""
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    spots = [os.environ.get("AEROGRAB_FFMPEG") or "", os.path.join(getattr(sys, "_MEIPASS", here), exe)]
    spots += [os.path.join(here, *p, exe) for p in ((), ("ffmpeg",), ("bin",))] + [os.path.join(CFG_DIR, exe)]
    for p in spots:
        if p and os.path.isdir(p):
            p = os.path.join(p, exe)
        if p and os.path.isfile(p):
            return p
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _ff_flags():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def run_ff(ff, args, timeout=None):
    try:
        return subprocess.run([ff, "-y", "-loglevel", "error", *args], capture_output=True, timeout=timeout, **_ff_flags()).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def merge_streams(ff, inputs, base, maps=False):
    """Mux (video + audio) or remux (one file) with stream copy into base.mp4. If the codecs don't fit MP4 (VP9/Opus...),
    re-encode only the audio to AAC, and as a last resort write base.mkv. Returns the file written, or None."""
    ins = [x for p in inputs for x in ("-i", p)]
    mp = ["-map", "0:v:0", "-map", "1:a:0"] if maps and len(inputs) == 2 else []
    for ext, codec in ((".mp4", ["-c", "copy", "-movflags", "+faststart"]),
                       (".mp4", ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]),
                       (".mkv", ["-c", "copy"])):
        dst = base + ext
        if run_ff(ff, [*ins, *mp, *codec, dst]) and os.path.isfile(dst) and os.path.getsize(dst) > 0:
            return dst
        try:
            os.remove(dst)
        except OSError:
            pass
    return None


# ---- addresses, file names, MIME types, magic bytes
_DRIVE = re.compile(r"^https?://drive\.google\.com/(?:file/(?:u/\d+/)?d/([\w-]+)|(?:open|uc)\?(?:[^#]*&)?id=([\w-]+))", re.I)


def normalize_url(u):
    """Google Drive share links (/file/d/ID/view, open?id=ID) become direct-download links."""
    m = _DRIVE.match((u or "").strip())
    if m and "export=download" not in u:
        return "https://drive.google.com/uc?export=download&id=" + (m.group(1) or m.group(2))
    return u


def is_drive_host(host):
    host = (host or "").lower()
    return host in ("drive.google.com", "docs.google.com") or host.endswith("usercontent.google.com")


def drive_confirm_url(page, base):
    """Drive answers big files with a web page ('can't scan for viruses'); the real link is in its form."""
    f = re.search(r'<form[^>]+id="download-form"[^>]*action="([^"]+)"', page) or re.search(r'<form[^>]+action="([^"]*download[^"]*)"', page)
    if f:
        q = dict(re.findall(r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"', page))
        act = html.unescape(f.group(1))
        return act + ("&" if "?" in act else "?") + urllib.parse.urlencode({k: html.unescape(v) for k, v in q.items()})
    m = re.search(r'href="(/uc\?export=download[^"]+)"', page)
    if m:
        return urllib.parse.urljoin(base, html.unescape(m.group(1)))
    return None


def name_from_url(u):
    """File name hidden in a link: the path's last part, else ?filename=... / S3's response-content-disposition."""
    p = urllib.parse.urlparse(u)
    n = urllib.parse.unquote(os.path.basename(p.path))
    if os.path.splitext(n)[1]:
        return n
    q = urllib.parse.parse_qs(p.query)
    for v in q.get("response-content-disposition", []):
        m = Message()
        m["content-disposition"] = v
        if m.get_filename():
            return m.get_filename()
    for k in ("filename", "file", "fname", "name", "download", "title"):
        for v in q.get(k, []):
            v = os.path.basename(v.replace("\\", "/"))
            if 1 < len(os.path.splitext(v)[1]) <= 6:
                return v
    return n


CT_EXT = {
    "application/pdf": ".pdf", "application/x-pdf": ".pdf",
    "application/x-msdownload": ".exe", "application/x-dosexec": ".exe", "application/vnd.microsoft.portable-executable": ".exe",
    "application/x-msdos-program": ".exe", "application/exe": ".exe", "application/x-msi": ".msi", "application/x-ms-installer": ".msi",
    "application/zip": ".zip", "application/x-zip-compressed": ".zip", "application/x-zip": ".zip",
    "application/x-rar-compressed": ".rar", "application/vnd.rar": ".rar", "application/x-rar": ".rar", "application/x-7z-compressed": ".7z",
    "application/gzip": ".gz", "application/x-gzip": ".gz", "application/x-tar": ".tar", "application/x-bzip2": ".bz2", "application/x-xz": ".xz",
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/aac": ".aac", "audio/wav": ".wav",
    "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/ogg": ".ogg", "audio/flac": ".flac", "audio/x-flac": ".flac", "audio/opus": ".opus",
    "video/mp4": ".mp4", "video/webm": ".webm", "video/x-matroska": ".mkv", "video/quicktime": ".mov", "video/x-msvideo": ".avi",
    "video/mpeg": ".mpg", "video/x-flv": ".flv", "video/3gpp": ".3gp", "video/mp2t": ".ts",
    "application/vnd.android.package-archive": ".apk", "application/x-apple-diskimage": ".dmg", "application/x-iso9660-image": ".iso",
    "application/x-debian-package": ".deb", "application/x-rpm": ".rpm", "application/epub+zip": ".epub",
    "application/msword": ".doc", "application/vnd.ms-excel": ".xls", "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/rtf": ".rtf", "application/json": ".json", "text/plain": ".txt", "text/csv": ".csv", "text/html": ".html", "application/xhtml+xml": ".html",
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp", "image/svg+xml": ".svg", "image/bmp": ".bmp",
    "image/tiff": ".tif", "image/heic": ".heic", "image/avif": ".avif", "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico",
}
GENERIC_CT = {"", "application/octet-stream", "binary/octet-stream", "application/force-download", "application/x-download",
              "application/download", "application/unknown", "application/x-unknown", "application/save", "application/x-www-form-urlencoded"}
DYNAMIC_EXT = {".php", ".php3", ".php4", ".asp", ".aspx", ".ashx", ".axd", ".jsp", ".jspx", ".cgi", ".pl", ".do", ".action"}  # scripts that hand out files
BINARY_EXT = {e for c in DEFAULT_CATEGORIES for e in c["exts"]} - {"txt", "csv", "sh", "bat", "svg"}  # a name like this must not turn out to be a web page


def magic_ext(head):
    """Extension from the first bytes of a file ('ole' for old Office/MSI containers, '' when unknown)."""
    h = head or b""
    if h.startswith(b"%PDF-"):
        return ".pdf"
    if h.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        return ".zip"
    if h.startswith(b"Rar!\x1a\x07"):
        return ".rar"
    if h.startswith(b"7z\xbc\xaf\x27\x1c"):
        return ".7z"
    if h.startswith(b"\x1f\x8b\x08"):
        return ".gz"
    if h.startswith(b"BZh") and h[4:10] == b"1AY&SY":
        return ".bz2"
    if h.startswith(b"\xfd7zXZ\x00"):
        return ".xz"
    if h[257:262] == b"ustar":
        return ".tar"
    if h.startswith(b"MZ") and len(h) >= 0x40:
        pe = int.from_bytes(h[0x3C:0x40], "little")
        if (pe + 4 <= len(h) and h[pe:pe + 4] == b"PE\0\0") or (pe + 4 > len(h) and pe < 4096):
            return ".exe"
    if h.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole"
    if h.startswith(b"ID3"):
        return ".mp3"
    if len(h) >= 3 and h[0] == 0xFF and h[1] in (0xFB, 0xF3, 0xF2) and (h[2] >> 4) not in (0, 15) and ((h[2] >> 2) & 3) != 3:
        return ".mp3"
    if h.startswith(b"fLaC"):
        return ".flac"
    if h.startswith(b"OggS"):
        return ".ogg"
    if h[:4] == b"RIFF" and h[8:12] == b"WAVE":
        return ".wav"
    if h[:4] == b"RIFF" and h[8:12] == b"AVI ":
        return ".avi"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return ".webp"
    if h[4:8] == b"ftyp":
        brand = h[8:12]
        return ".m4a" if brand in (b"M4A ", b"M4B ") else ".mov" if brand == b"qt  " else ".mp4"
    if h.startswith(b"\x1aE\xdf\xa3"):
        return ".webm" if b"webm" in h[:64] else ".mkv"
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if h.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if h.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if h.startswith(b"{\\rtf"):
        return ".rtf"
    return ""


def sniff_ext(head, ct="", where=""):
    """Best extension from Content-Type and the file's first bytes ('' if neither says)."""
    base = (ct or "").split(";")[0].strip().lower()
    byct = CT_EXT.get(base)
    if byct is None and base and base not in GENERIC_CT and not base.startswith("text/"):
        g = mimetypes.guess_extension(base)
        byct = {".jpe": ".jpg", ".jpeg": ".jpg", ".htm": ".html"}.get(g, g)
    if byct and byct not in (".txt", ".html"):
        return byct
    m = magic_ext(head)
    if m == "ole":  # old Office files and MSI installers share one container: only the name or type can tell
        return ".msi" if re.search(r"(?i)(^|[^a-z])msi([^a-z]|$)", where or "") else ""
    return m or byct or ""


def fix_name(name, ct="", head=b"", where=""):
    """Give a file a proper extension when the server's name has none (or a script's: download.php): '12345' -> '12345.pdf'."""
    stem, ext = os.path.splitext(name)
    e = ext.lower()
    if e and e not in DYNAMIC_EXT:
        return name
    guess = sniff_ext(head, ct, where)
    if not guess:
        return name
    return (stem if e else name) + guess


def looks_like_page(head, ct=""):
    """True when the bytes are a web page (an error / login / expired-link page) rather than a file."""
    if magic_ext(head):
        return False
    h = (head or b"").lstrip()[:20].lower()
    return h.startswith((b"<!doctype html", b"<html", b"<head", b"<body")) or (ct or "").split(";")[0].strip().lower() in ("text/html", "application/xhtml+xml")


# ---- yt-dlp (optional): finds the real streams behind YouTube, Facebook, Instagram, Vimeo, TikTok ...
YT_MISSING = "yt-dlp is not installed - run:  pip install yt-dlp   (needed for YouTube, Facebook, Instagram and other video sites)"
MEDIA_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com", "facebook.com", "fb.watch", "instagram.com", "vimeo.com", "dailymotion.com",
               "twitter.com", "x.com", "tiktok.com", "twitch.tv", "reddit.com", "v.redd.it", "soundcloud.com", "bilibili.com", "streamable.com",
               "rumble.com", "ok.ru", "vk.com", "bandcamp.com", "odysee.com")
_IES = {}


# ---- yt-dlp's environment: keeping it current, the JavaScript runtime and the solver that YouTube now needs ----
# Why this exists. YouTube changes its player every few weeks, so a copy of yt-dlp that is a few months old stops working. Since
# yt-dlp 2025.11 YouTube ALSO needs an external JavaScript runtime (Deno, Node >= 22, Bun or QuickJS) plus the yt-dlp-ejs solver to
# unlock the real stream links; without them the quality list is empty or stuck at 360p. AeroGrab looks after both by itself:
#   * find_js_runtime()    finds Deno / Node / Bun / QuickJS (our own folder, PATH, the usual install spots)
#   * install_deno()       fetches Deno (one small executable, official GitHub release) into ~/.aerograb/runtime when nothing is installed
#   * ytdlp_update()       downloads the official yt-dlp zipapp (checksum verified) into ~/.aerograb/ytdlp and uses it instead of the bundled copy
#   * explain_ytdlp_error() turns yt-dlp's wall of text into a code + a sentence the browser menu can show
# Opt out:  settings.json "auto_ytdlp_update": false / "auto_js_runtime": false, or env AEROGRAB_NO_YTDLP_UPDATE=1 / AEROGRAB_NO_RUNTIME_DOWNLOAD=1.
YT_ENV = {"installing": False, "runtime_error": "", "update_error": "", "updated": ""}
_YT_LOCK = threading.RLock()
_YT = {"checked": False}
_JS = {"done": False, "rt": None}
RUNTIME_MIN_MAJOR = {"deno": 2, "node": 22}  # the first version yt-dlp accepts
UPDATE_EVERY = 12 * 3600
GH_LATEST = "https://api.github.com/repos/{}/releases/latest"


def _runtime_dir():
    return os.path.join(CFG_DIR, "runtime")


def _ytdlp_dir():
    return os.path.join(CFG_DIR, "ytdlp")


def _ytdlp_zip():
    return os.path.join(_ytdlp_dir(), "yt-dlp.zip")


def _yt_setting(key, default):
    try:
        with open(os.path.join(CFG_DIR, "settings.json"), encoding="utf-8") as f:
            return json.load(f).get(key, default)
    except (OSError, ValueError, AttributeError):
        return default


def _vkey(v):
    """'2026.03.02' / '2026.03.02.232212' -> comparable tuple."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v or ""))[:4])


def _http_get(url, timeout=60, limit=300 << 20, accept=None):
    """GET through AeroGrab's own connection layer (so the proxy settings apply). Returns bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Accept": accept} if accept else {})})
    buf = bytearray()
    with OPENER.open(req, timeout=timeout) as r:
        while True:
            c = r.read(1 << 16)
            if not c:
                break
            buf += c
            if len(buf) > limit:
                raise IOError("download is larger than expected")
    return bytes(buf)


# ---------- JavaScript runtime ----------
def _run_version(path):
    """(major, minor) printed by `<runtime> --version`, or None when it doesn't run."""
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=20, **_ff_flags()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+)\.(\d+)", out or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _runtime_candidates():
    exe = lambda n: n + (".exe" if os.name == "nt" else "")
    home = os.path.expanduser("~")
    out = []
    env = os.environ.get("AEROGRAB_JS_RUNTIME") or ""
    if env and os.path.isfile(env):
        stem = os.path.splitext(os.path.basename(env))[0].lower()
        out.append(({"qjs": "quickjs"}.get(stem, stem), env))
    for name in ("deno", "node", "bun", "quickjs"):
        binary = "qjs" if name == "quickjs" else name
        spots = []
        if name == "deno":
            spots += [os.path.join(_runtime_dir(), exe("deno")), os.path.join(home, ".deno", "bin", exe("deno"))]
            if os.name == "nt":
                spots.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "deno.exe"))
        spots.append(shutil.which(binary) or "")
        if name == "node" and os.name == "nt":
            spots.append(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs", "node.exe"))
        out += [(name, p) for p in spots if p and os.path.isfile(p)]
    return out


def find_js_runtime(refresh=False):
    """The JavaScript runtime yt-dlp should use: {'name': 'deno'|'node'|'bun'|'quickjs', 'path': ...}, or None."""
    with _YT_LOCK:
        if _JS["done"] and not refresh and (_JS["rt"] is None or os.path.isfile(_JS["rt"]["path"])):
            return _JS["rt"]
        rt = None
        for name, path in _runtime_candidates():
            need = RUNTIME_MIN_MAJOR.get(name)
            if need:
                v = _run_version(path)
                if not v or v[0] < need:
                    continue  # too old for yt-dlp (Node < 22, Deno < 2) - keep looking
            rt = {"name": name, "path": path}
            break
        _JS.update(done=True, rt=rt)
        if rt:  # a runtime found by full path must also be findable by name
            d = os.path.dirname(rt["path"])
            if d and d not in os.environ.get("PATH", "").split(os.pathsep):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        return rt


def deno_asset(system=None, machine=None):
    system, m = system or platform.system(), (machine or platform.machine()).lower()
    arch = "aarch64" if m in ("arm64", "aarch64") else "x86_64"
    if system == "Windows":
        return f"deno-{arch}-pc-windows-msvc.zip"
    if system == "Darwin":
        return f"deno-{arch}-apple-darwin.zip"
    return f"deno-{arch}-unknown-linux-gnu.zip"


def install_deno(fetch=None):
    """Put Deno (a single executable, official release) into ~/.aerograb/runtime. Returns its path; raises IOError."""
    import zipfile
    fetch = fetch or _http_get
    url = "https://github.com/denoland/deno/releases/latest/download/" + deno_asset()
    data = fetch(url, 180)
    try:  # the release publishes a checksum next to each archive; use it when it is there
        want = fetch(url + ".sha256sum", 30, 4096).decode("ascii", "replace").split()[0].lower()
    except Exception:
        want = ""
    if re.fullmatch(r"[0-9a-f]{64}", want) and hashlib.sha256(data).hexdigest() != want:
        raise IOError("the Deno download failed its checksum")
    exe = "deno.exe" if os.name == "nt" else "deno"
    os.makedirs(_runtime_dir(), exist_ok=True)
    dst = os.path.join(_runtime_dir(), exe)
    tmp = dst + ".part"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            member = next((n for n in z.namelist() if os.path.basename(n) == exe), None)
            if not member:
                raise IOError("unexpected Deno archive")
            with z.open(member) as src, open(tmp, "wb") as out:
                shutil.copyfileobj(src, out)
        os.chmod(tmp, 0o755)
        os.replace(tmp, dst)
    except zipfile.BadZipFile:
        raise IOError("the Deno download was damaged")
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    v = _run_version(dst)
    if not v or v[0] < RUNTIME_MIN_MAJOR["deno"]:
        raise IOError("the downloaded Deno does not run on this computer")
    return dst


def ensure_js_runtime_async():
    """If no runtime exists, fetch Deno in the background. Returns True when a download was started."""
    with _YT_LOCK:
        if YT_ENV["installing"] or find_js_runtime():
            return False
        if not _yt_setting("auto_js_runtime", True) or os.environ.get("AEROGRAB_NO_RUNTIME_DOWNLOAD"):
            return False
        YT_ENV["installing"] = True

    def run():
        try:
            install_deno()
            find_js_runtime(refresh=True)
            YT_ENV["runtime_error"] = ""
        except Exception as e:
            YT_ENV["runtime_error"] = str(e)
        finally:
            YT_ENV["installing"] = False
    threading.Thread(target=run, daemon=True).start()
    return True


# ---------- keeping yt-dlp itself current ----------
def _read_zip_version(path):
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            m = re.search(rb"__version__\s*=\s*['\"]([^'\"]+)", z.read("yt_dlp/version.py"))
        return m.group(1).decode() if m else ""
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""


def _installed_ytdlp_version():
    """Version of the yt-dlp that is installed (not the downloaded copy), without importing it when possible."""
    m = sys.modules.get("yt_dlp")
    if m is not None and _ytdlp_zip() not in str(getattr(m, "__file__", "")):
        v = getattr(getattr(m, "version", None), "__version__", "")
        if v:
            return v
    try:
        import importlib.metadata as md
        return md.version("yt-dlp")
    except Exception:
        return ""


def _purge_ytdlp():
    for k in [k for k in sys.modules if k == "yt_dlp" or k.startswith("yt_dlp.")]:
        del sys.modules[k]
    _IES.clear()
    import importlib
    importlib.invalidate_caches()


def _prefer_downloaded_ytdlp():
    """Make the downloaded zipapp the yt-dlp that gets imported when it is newer than the installed one."""
    z = _ytdlp_zip()
    if os.environ.get("AEROGRAB_NO_YTDLP_UPDATE") or not os.path.isfile(z):
        return False
    zv, cur = _read_zip_version(z), _installed_ytdlp_version()
    if not zv or (cur and _vkey(cur) >= _vkey(zv)):
        return False
    if z not in sys.path:
        sys.path.insert(0, z)
    return True


def _ytdlp():
    for n in ("stdout", "stderr"):  # a --noconsole / --windowed build has no stdout or stderr, and yt-dlp writes to them
        if getattr(sys, n, None) is None:
            setattr(sys, n, open(os.devnull, "w"))
    with _YT_LOCK:
        if not _YT["checked"]:
            _YT["checked"] = True
            try:
                _prefer_downloaded_ytdlp()
            except Exception:
                pass
        try:
            import yt_dlp
            return yt_dlp
        except ImportError:
            z = _ytdlp_zip()
            if z in sys.path:  # the downloaded copy is broken: forget it and use the installed one
                sys.path.remove(z)
                _purge_ytdlp()
                try:
                    os.replace(z, z + ".bad")
                except OSError:
                    pass
                try:
                    import yt_dlp
                    return yt_dlp
                except ImportError:
                    pass
            return None


def ytdlp_version():
    y = _ytdlp()
    if y is None:
        return ""
    try:
        from yt_dlp.version import __version__
        return str(__version__)
    except Exception:
        return str(getattr(getattr(y, "version", None), "__version__", ""))


def ytdlp_update(force=False, fetch=None, channel=None):
    """Download the newest official yt-dlp (zipapp, SHA-256 verified) when it is newer than what runs now, and switch to it.
    Returns {'updated': bool, 'version': str, 'skipped': bool, 'error': str}. Checks at most every 12 h unless forced."""
    fetch = fetch or _http_get
    channel = channel or _yt_setting("ytdlp_channel", "stable")
    repo = "yt-dlp/yt-dlp-nightly-builds" if channel == "nightly" else "yt-dlp/yt-dlp"
    sf = os.path.join(_ytdlp_dir(), "state.json")
    try:
        with open(sf, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    if not force and time.time() - float(st.get("checked") or 0) < UPDATE_EVERY and st.get("channel") == channel:
        return {"updated": False, "skipped": True, "version": "", "error": ""}
    res = {"updated": False, "skipped": False, "version": "", "error": ""}
    try:
        tag = str(json.loads(fetch(GH_LATEST.format(repo), 30, 1 << 20, "application/vnd.github+json"))["tag_name"])
        if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(\.\d+)?", tag):
            raise IOError("unexpected release name " + tag[:30])
        res["version"] = tag
        have = ytdlp_version() or _installed_ytdlp_version()
        if not have or _vkey(tag) > _vkey(have):
            base = f"https://github.com/{repo}/releases/download/{tag}/"
            data = fetch(base + "yt-dlp", 120, 40 << 20)
            sums = fetch(base + "SHA2-256SUMS", 30, 1 << 16).decode("ascii", "replace")
            want = next((ln.split()[0].lower() for ln in sums.splitlines() if ln.split()[-1:] == ["yt-dlp"]), "")
            if not re.fullmatch(r"[0-9a-f]{64}", want) or hashlib.sha256(data).hexdigest() != want:
                raise IOError("the yt-dlp download failed its checksum")
            os.makedirs(_ytdlp_dir(), exist_ok=True)
            tmp = _ytdlp_zip() + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            if _read_zip_version(tmp) != tag:
                os.remove(tmp)
                raise IOError("the downloaded yt-dlp is not the release it claims to be")
            os.replace(tmp, _ytdlp_zip())
            with _YT_LOCK:  # switch the running program to it
                _purge_ytdlp()
                z = _ytdlp_zip()
                if z not in sys.path:
                    sys.path.insert(0, z)
            res["updated"] = bool(_ytdlp())
            YT_ENV["updated"] = tag if res["updated"] else ""
        st = {"checked": time.time(), "channel": channel, "latest": tag}
        os.makedirs(_ytdlp_dir(), exist_ok=True)
        with open(sf, "w", encoding="utf-8") as f:
            json.dump(st, f)
        YT_ENV["update_error"] = ""
    except Exception as e:
        res["error"] = str(e)
        YT_ENV["update_error"] = str(e)
    return res


def ytdlp_status():
    y = _ytdlp()
    rt = find_js_runtime()
    return {"installed": y is not None, "version": ytdlp_version(), "downloaded_copy_in_use": bool(y and _ytdlp_zip() in str(getattr(y, "__file__", ""))),
            "runtime": rt["name"] if rt else "", "runtime_path": rt["path"] if rt else "", "installing_runtime": YT_ENV["installing"],
            "runtime_error": YT_ENV["runtime_error"], "update_error": YT_ENV["update_error"]}


def ensure_ytdlp_env():
    """Called once in the background at start-up."""
    try:
        find_js_runtime()
        if _yt_setting("auto_ytdlp_update", True) and not os.environ.get("AEROGRAB_NO_YTDLP_UPDATE"):
            ytdlp_update()
        ensure_js_runtime_async()
    except Exception:
        pass


# ---------- what went wrong, in words ----------
_YT_ERRORS = (
    ("js_runtime", r"javascript runtime|js runtime|no supported javascript|yt-dlp-ejs|\bejs\b|challenge solv|n.?challenge|nsig|signature (?:solving|extraction)|jsc",
     "YouTube needs a JavaScript runtime that AeroGrab could not find. AeroGrab installs Deno by itself - wait a minute and try again, or install Deno (winget install DenoLand.Deno) or Node.js 22+."),
    ("bot", r"not a bot",
     "YouTube is asking for proof that you are a person. Open YouTube in your browser while signed in, play the video once, then try again (AeroGrab sends your browser's cookies)."),
    ("age", r"age.?restrict|confirm your age|inappropriate for some users",
     "This video is age-restricted. Sign in to YouTube in your browser, then try again."),
    ("login", r"private video|members.?only|join this channel|login required|log in|sign in|this video is private|requires? (?:a )?(?:login|authentication)|need to be logged",
     "This video needs you to be signed in. Sign in on the website in your browser, then try again."),
    ("geo", r"not available in your country|geo.?restrict|blocked it in your country|uploader has not made this video available",
     "The site does not allow this video in your country."),
    ("drm", r"\bdrm\b|widevine|playready|fairplay",
     "This video is DRM-protected. AeroGrab does not download protected content."),
    ("unavailable", r"video unavailable|has been removed|no longer available|does not exist|been terminated|deleted",
     "The video is no longer available."),
    ("format", r"requested format is not available|no video formats found|no formats",
     "The site gave no downloadable formats for this video (often a missing JavaScript runtime, an out-of-date yt-dlp, or a sign-in requirement)."),
    ("network", r"timed out|timeout|connection (?:reset|refused|aborted)|getaddrinfo|name or service|network is unreachable|ssl|certificate|proxy|temporary failure",
     "The connection to the site failed. Check your internet connection and proxy settings."),
    ("outdated", r"unable to extract|unsupported url|unexpected|http error 40[034]|precondition|player response|nsig|traceback|no video found",
     "The site probably changed and yt-dlp needs an update. AeroGrab updates it by itself - try again in a minute."),
)


def explain_ytdlp_error(msg):
    """(code, hint) for a yt-dlp error message. code: js_runtime, bot, age, login, geo, drm, unavailable, format, network, outdated or unknown."""
    low = re.sub(r"\s+", " ", str(msg or "")).lower()
    for code, pat, hint in _YT_ERRORS:
        if re.search(pat, low):
            return code, hint
    return "unknown", ""


def media_site(url):
    """True for video/audio pages that need yt-dlp to find the actual file (never for direct file links)."""
    p = urllib.parse.urlparse(url or "")
    host = (p.hostname or "").lower()
    if p.scheme not in ("http", "https") or not host or is_drive_host(host):
        return False
    if os.path.splitext(p.path)[1].lower().lstrip(".") in BINARY_EXT:
        return False
    if any(host == h or host.endswith("." + h) for h in MEDIA_HOSTS):
        return True
    y = _ytdlp()
    if y is None:
        return False
    try:  # yt-dlp's own site list: a local pattern match, no network
        if "ies" not in _IES:
            _IES["ies"] = [ie for ie in y.extractor.gen_extractor_classes() if not str(getattr(ie, "IE_NAME", "")).lower().startswith(("generic", "googledrive"))]
        return any(ie.suitable(url) for ie in _IES["ies"])
    except Exception:
        return False


def warm_up():
    """Load yt-dlp and its site list in the background at start-up, so the first 'Download this video' menu doesn't wait for the import."""
    try:
        media_site("https://www.example.com/watch?v=0")  # imports yt-dlp and builds the extractor list
        find_ffmpeg()
    except Exception:
        pass
    ensure_ytdlp_env()  # v1.8.1: newest yt-dlp + a JavaScript runtime for YouTube, in the background


def detect_kind(url):
    """Which engine a link needs: 'hls' (.m3u8), 'dash' (.mpd), 'ytdlp' (video sites), or None (plain file)."""
    low = (url or "").lower()
    if low.startswith(("ftp://", "ftps://")):
        return "ftp"
    if ".m3u8" in low:
        return "hls"
    if urllib.parse.urlparse(low).path.endswith(".mpd"):
        return "dash"
    return "ytdlp" if media_site(url) else None


def apply_cookies(ydl, cookie, url):
    """FIX: hand the browser's cookies to yt-dlp through its cookiejar, scoped to the page's domain, instead of a raw
    'Cookie' header (yt-dlp does not reliably forward that header, which broke logged-in / private Facebook videos)."""
    jar = getattr(ydl, "cookiejar", None)
    if not cookie or jar is None:
        return
    import http.cookiejar as cj
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if not host:
        return
    dom = "." + (host[4:] if host.startswith("www.") else host)
    for part in str(cookie).split(";"):
        name, eq, value = part.strip().partition("=")
        if not eq or not name:
            continue
        jar.set_cookie(cj.Cookie(0, name, value, None, False, dom, True, True, "/", True, True, None, True, None, None, {}))


def ytdlp_opts(quality=0, referer=None, cookie=None, ua=None, limit_kb=0):
    """Options shared by every yt-dlp call. FIX: separate best video + best audio, always merged by ffmpeg into one .mp4,
    so DASH sites (Facebook / Instagram / Reels) never end up silent. Cookies are applied with apply_cookies().
    v1.8.1: the JavaScript runtime + solver YouTube needs (see 'yt-dlp's environment'), parallel fragments, a speed limit."""
    q = int(quality or 0)
    h = f"[height<={q}]" if q > 0 else ""
    o = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": NET.timeout, "retries": max(0, NET.retries - 1),
         "fragment_retries": 10, "extractor_retries": 3, "concurrent_fragment_downloads": 4, "continuedl": True,
         "merge_output_format": "mp4",
         "format": "ba[ext=m4a]/ba/b" if q < 0 else f"bv*{h}[ext=mp4]+ba[ext=m4a]/bv*{h}+ba/b{h}/b"}  # quality -1 = audio only
    o["remote_components"] = ["ejs:github"]  # lets yt-dlp fetch the challenge solver when the yt-dlp-ejs package is missing or too old
    rt = find_js_runtime()
    if rt:
        o["js_runtimes"] = {rt["name"]: {"path": rt["path"]}}
    if limit_kb and int(limit_kb) > 0:
        o["ratelimit"] = int(limit_kb) * 1024
    ff = find_ffmpeg()
    if ff:
        o["ffmpeg_location"] = ff
    hdr = {k: v for k, v in (("User-Agent", ua), ("Referer", referer)) if v}
    if hdr:
        o["http_headers"] = hdr
    if OPENER.proxy_url:
        o["proxy"] = OPENER.proxy_url  # same proxy as the rest of AeroGrab
    elif OPENER.cfg.get("proxy_mode") == "none":
        o["proxy"] = ""  # explicitly direct
    return o


def summarize_formats(info):
    """What the browser's 'Download this video' menu shows: one entry per resolution (video + the best audio, sizes added up) and an audio-only entry."""
    dur = float(info.get("duration") or 0)

    def size(f):
        n = f.get("filesize") or 0
        if n:
            return int(n), False
        n = f.get("filesize_approx") or 0
        if n:
            return int(n), True
        tbr = f.get("tbr") or ((f.get("vbr") or 0) + (f.get("abr") or 0))
        return (int(tbr * 1000 / 8 * dur), True) if tbr and dur else (0, True)
    fl = [f for f in (info.get("formats") or [info]) if isinstance(f, dict) and f.get("ext") != "mhtml"
          and (f.get("protocol") or "") != "mhtml" and f.get("format_note") != "storyboard"]
    video = [f for f in fl if (f.get("height") or 0) > 0 and f.get("vcodec") != "none"]
    audio = [f for f in fl if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    a = max(audio, key=lambda f: (f.get("ext") == "m4a", f.get("abr") or 0, size(f)[0]), default=None)
    asz, aap = size(a) if a else (0, False)
    best = {}
    for f in video:
        key = (bool(f.get("filesize") or f.get("filesize_approx")), f.get("ext") == "mp4", f.get("tbr") or 0)
        h = int(f["height"])
        if h not in best or key > best[h][0]:
            best[h] = (key, f)
    out = []
    for h in sorted(best, reverse=True):
        f = best[h][1]
        sz, ap = size(f)
        mux = f.get("acodec") in (None, "none")  # picture only: the audio is fetched separately and merged
        out.append({"height": h, "fps": int(f.get("fps") or 0), "ext": "mp4" if mux else (f.get("ext") or "mp4"),
                    "size": sz + (asz if mux else 0), "approx": bool(ap or (mux and aap))})
    return {"title": pick_title(info), "fallback": fallback_title(info), "duration": dur, "formats": out,
            "audio": {"ext": a.get("ext") or "m4a", "size": asz, "approx": aap} if a else None}


_TITLE_SITES = "YouTube|Facebook|Instagram|TikTok|Twitter|X|Vimeo|Dailymotion|Reddit|Twitch|Bilibili|Rumble|Streamable"
_TITLE_TAIL = re.compile(r"\s*[-|\u2013\u2014\u00b7]\s*(?:" + _TITLE_SITES + r")\s*$", re.I)
_GENERIC_TITLE = re.compile(r"^(?:" + _TITLE_SITES.lower() + r"|home|watch|reels?|video|videos|stories|story|untitled|log ?in.*|sign ?in.*"
                            r"|(?:facebook|instagram|tiktok|youtube) (?:video|reel|reels|watch)|(?:video|reel|photo) by .*|.* on (?:instagram|facebook|tiktok)"
                            r"|\(\d+\+?\) .*)$", re.I)


def is_generic_title(t):
    """True for titles that only name the site (Facebook, 'Video', 'Reel by X' ...): they say nothing about the media."""
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return len(t) < 3 or bool(_GENERIC_TITLE.match(_TITLE_TAIL.sub("", t).strip())) or bool(re.fullmatch(r"[\d\W_]+", t))


def shorten_title(t, n=100):
    """At most n characters, cut at a word boundary, no dangling punctuation or ellipsis."""
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    if len(t) <= n:
        return t.rstrip(" .\u2026")
    cut = t[:n]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp >= n * 0.6 else cut).rstrip(" .,;:-\u2026")


def pick_title(info):
    """The best real title yt-dlp knows, in this order: the site's own title, its full title, an alternative title, the first line of the
    caption / description, the track name. Titles that only name the site are skipped. '' when nothing useful exists."""
    first_line = next((ln.strip() for ln in str(info.get("description") or "").splitlines() if len(ln.strip()) >= 3), "")
    ident = str(info.get("id") or "")
    for c in (info.get("title"), info.get("fulltitle"), info.get("alt_title"), first_line, info.get("track")):
        t = _TITLE_TAIL.sub("", re.sub(r"\s+", " ", str(c or "")).strip()).strip()
        if t and t != ident and not is_generic_title(t):
            return shorten_title(t)
    return ""


def fallback_title(info):
    """A clean, descriptive name when the site gave no usable title: '<Site> video <id>'."""
    site = str(info.get("extractor_key") or info.get("extractor") or "").split(":")[0]
    if not site:
        host = (urllib.parse.urlparse(str(info.get("webpage_url") or "")).hostname or "").lower()
        site = host[4:] if host.startswith("www.") else host
    site = site.split(".")[0].capitalize() if "." in site else site
    ident = str(info.get("id") or "").strip()
    return clean_name(" ".join(x for x in (site or "", "video", ident[:40]) if x)) if (site or ident) else "video"


def is_youtube_url(url):
    h = (urllib.parse.urlparse(url or "").hostname or "").lower()
    return any(h == d or h.endswith("." + d) for d in ("youtube.com", "youtu.be", "youtube-nocookie.com"))


def ytdlp_formats(url, referer=None, cookie=None, ua=None):
    y = _ytdlp()
    if y is None:
        raise IOError(YT_MISSING)
    opts = dict(ytdlp_opts(0, referer, cookie, ua), skip_download=True)
    opts.pop("format")
    with y.YoutubeDL(opts) as ydl:
        apply_cookies(ydl, cookie, url)  # FIX: cookies via cookiejar
        info = ydl.extract_info(url, download=False)
    if info and info.get("entries"):
        info = next((e for e in info["entries"] if e), None)
    if not info:
        raise IOError("yt-dlp found no video at this address")
    out = summarize_formats(info)
    # YouTube without a JavaScript runtime still answers - with a handful of low-quality formats. Say so instead of looking broken.
    if is_youtube_url(url) and not find_js_runtime() and max([f["height"] for f in out["formats"]] or [0]) <= 360:
        out["warning"] = ("Only low qualities are offered because no JavaScript runtime was found. " +
                          ("AeroGrab is installing Deno right now - try again in a minute." if YT_ENV["installing"] else
                           "Install Deno (winget install DenoLand.Deno) or Node.js 22+ and restart AeroGrab."))
    return out


_PLAIN_HEADERS = {"user-agent", "accept", "accept-language", "accept-encoding", "sec-fetch-mode", "referer"}


def needs_ytdlp_downloader(page_url, fmts):
    """True when the stream links yt-dlp found can only be fetched the way yt-dlp fetches them: YouTube (signed links that are throttled or
    refused for big / parallel range requests - yt-dlp asks for ~10 MB pieces), links that need cookies or headers AeroGrab's engine doesn't send,
    or anything with downloader options of its own."""
    if is_youtube_url(page_url):
        return True
    for f in fmts:
        host = (urllib.parse.urlparse(f.get("url") or "").hostname or "").lower()
        if host.endswith(("googlevideo.com", "youtube.com")) or f.get("downloader_options") or f.get("cookies"):
            return True
        if any(str(k).lower() not in _PLAIN_HEADERS for k in (f.get("http_headers") or {})):
            return True
    return False


def ytdlp_resolve(url, quality=0, referer=None, cookie=None, ua=None):
    """Ask yt-dlp for the best stream(s). Returns {kind: direct|mux|hls|native, url, audio, name, title, referer, ua}."""
    y = _ytdlp()
    if y is None:
        raise IOError(YT_MISSING)
    with y.YoutubeDL(dict(ytdlp_opts(quality, referer, cookie, ua), skip_download=True)) as ydl:
        apply_cookies(ydl, cookie, url)  # FIX: cookies via cookiejar
        info = ydl.extract_info(url, download=False)
    if info and info.get("entries"):  # a playlist link: take its first video
        info = next((e for e in info["entries"] if e), None)
    if not info:
        raise IOError("yt-dlp found no downloadable media at this address")
    fmts = info.get("requested_formats") or [info]
    kinds = ["http" if (f.get("protocol") or "https").lower() in ("http", "https") else "hls" if (f.get("protocol") or "").lower().startswith("m3u8") else "other" for f in fmts]
    title = clean_name(pick_title(info) or fallback_title(info))
    hdr = fmts[0].get("http_headers") or info.get("http_headers") or {}
    plan = {"title": title, "referer": hdr.get("Referer") or referer, "ua": hdr.get("User-Agent") or ua, "url": "", "audio": "",
            "kind": "native", "name": title + ".mp4"}
    if needs_ytdlp_downloader(url, fmts):
        return plan  # yt-dlp's own downloader fetches it (NativeYt)
    if len(fmts) == 1 and kinds[0] == "http" and fmts[0].get("url"):
        plan.update(kind="direct", url=fmts[0]["url"], name=f"{title}.{fmts[0].get('ext') or 'mp4'}")
    elif len(fmts) == 2 and kinds == ["http", "http"] and all(f.get("url") for f in fmts):
        v = next((f for f in fmts if f.get("vcodec") not in (None, "none")), fmts[0])
        a = next(f for f in fmts if f is not v)
        plan.update(kind="mux", url=v["url"], audio=a["url"])
    elif len(fmts) == 1 and kinds[0] == "hls" and fmts[0].get("url"):
        plan.update(kind="hls", url=fmts[0]["url"])
    return plan


# ============================ wave 2: antivirus, smart links, clipboard history, toolbar layout ============================
# Everything in this block is plain Python (no tkinter), so it is unit-tested without a display.

# ---------- antivirus: ask an engine that is already installed; AeroGrab bundles none ----------
AV_TIMEOUT = 600  # seconds one scan may take before it is given up
AV_NAMES = {"defender": "Windows Defender", "clamav": "ClamAV"}


def _version_key(path):
    return tuple(int(x) for x in re.findall(r"\d+", os.path.basename(os.path.dirname(path)))) or (0,)


def find_av(prefer="auto", system=None, env=None, which=shutil.which, isfile=os.path.isfile, globber=glob.glob):
    """Locate an installed scanner. Returns (engine, path) or None. engine: 'defender' (MpCmdRun.exe) or 'clamav' (clamscan).
    prefer: 'auto' (Defender first, then ClamAV), 'defender' or 'clamav' (only that one)."""
    system = system or platform.system()
    env = os.environ if env is None else env
    defender = clam = None
    if system == "Windows":
        plat = sorted(globber(os.path.join(env.get("ProgramData") or r"C:\ProgramData", "Microsoft", "Windows Defender", "Platform", "*", "MpCmdRun.exe")), key=_version_key)
        cands = plat[-1:] + [os.path.join(env.get("ProgramFiles") or r"C:\Program Files", "Windows Defender", "MpCmdRun.exe")]
        defender = next((c for c in cands if isfile(c)), None) or which("MpCmdRun.exe")
    clam_c = [which("clamscan"), which("clamscan.exe")]
    if system == "Windows":
        clam_c += [os.path.join(env.get(k) or "", "ClamAV", "clamscan.exe") for k in ("ProgramFiles", "ProgramFiles(x86)")]
    elif system == "Darwin":
        clam_c += ["/opt/homebrew/bin/clamscan", "/usr/local/bin/clamscan"]
    clam = next((c for c in clam_c if c and isfile(c)), None)
    found = {"defender": defender, "clamav": clam}
    for name in ([prefer] if prefer in found else ["defender", "clamav"]):
        if found[name]:
            return name, found[name]
    return None


def av_command(engine, exe, path):
    if engine == "defender":
        # -ScanType 3 = custom scan of one file; -DisableRemediation = report only, never delete or quarantine behind the user's back
        return [exe, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"]
    return [exe, "--no-summary", path]


def parse_av(engine, code, out):
    """(state, threat) from an engine's exit code and output. state: 'clean' | 'infected' | 'error'."""
    if engine == "defender":  # MpCmdRun: 0 = no threats, 2 = threats found
        if code == 0:
            return "clean", ""
        if code == 2:
            names = [n.strip() for n in re.findall(r"^\s*Threat\s*:\s*(.+?)\s*$", out, re.M)]
            return "infected", ", ".join(dict.fromkeys(names)) or "a threat"
        return "error", ""
    if code == 0:  # clamscan: 0 = clean, 1 = virus found, 2 = error
        return "clean", ""
    if code == 1:
        names = [n.strip() for n in re.findall(r"^.*?:\s+(\S.*?)\s+FOUND\s*$", out, re.M)]  # ": " (not the ":" of a drive letter like C:\)
        return "infected", ", ".join(dict.fromkeys(names)) or "a threat"
    return "error", ""


def scan_file(path, prefer="auto", runner=subprocess.run, finder=find_av, timeout=AV_TIMEOUT):
    """Scan one file with the installed antivirus. Returns {'state': clean|infected|error|unavailable, 'engine', 'threat', 'detail'}."""
    found = finder(prefer)
    if not found:
        return {"state": "unavailable", "engine": "", "threat": "", "detail": "No antivirus found (Windows Defender or ClamAV)."}
    engine, exe = found
    res = {"state": "error", "engine": engine, "threat": "", "detail": ""}
    if not path or not os.path.isfile(path):
        res["detail"] = "The file is gone."
        return res
    try:
        r = runner(av_command(engine, exe, path), capture_output=True, text=True, errors="replace", timeout=timeout, **_ff_flags())
    except subprocess.TimeoutExpired:
        res["detail"] = f"{AV_NAMES[engine]} took longer than {timeout // 60} minutes."
        return res
    except (OSError, subprocess.SubprocessError) as e:
        res["detail"] = f"Couldn't start {AV_NAMES[engine]}: {e}"
        return res
    state, threat = parse_av(engine, r.returncode, (r.stdout or "") + "\n" + (r.stderr or ""))
    res.update(state=state, threat=threat)
    if state == "error":
        res["detail"] = f"{AV_NAMES[engine]} stopped with error code {r.returncode}."
    return res


def av_summary(res):
    """One line for the Download complete dialog / properties."""
    name = AV_NAMES.get(res.get("engine"), "")
    return {"clean": f"{name}: no threats found.", "infected": f"WARNING: {name} found {res.get('threat') or 'a threat'}.",
            "error": f"The virus scan didn't finish. {res.get('detail', '')}".strip(),
            "unavailable": "Not scanned: no antivirus found (Windows Defender or ClamAV)."}.get(res.get("state"), "")


# ---------- smart links: find the real file behind redirects, shorteners and download pages ----------
_WRAPPERS = (  # (host, path prefix, query keys that carry the real address): well-known "you are leaving" redirectors
    ("google.com", "/url", ("q", "url")), ("facebook.com", "/l.php", ("u",)), ("out.reddit.com", "", ("url",)),
    ("safelinks.protection.outlook.com", "", ("url",)), ("youtube.com", "/redirect", ("q",)), ("steamcommunity.com", "/linkfilter", ("url", "u")),
    ("vk.com", "/away.php", ("to",)), ("disq.us", "/url", ("url",)), ("slack-redir.net", "", ("url",)), ("l.instagram.com", "", ("u",)))
_REDIRECTOR_WORDS = {"redirect", "redir", "away", "away.php", "out", "go", "goto", "click", "link", "url", "exit", "r", "l", "l.php", "jump", "leave", "external", "outbound", "redirect.php"}
_WRAP_KEYS = ("url", "u", "q", "target", "dest", "destination", "redirect", "redirect_url", "redirect_uri", "link", "to", "goto", "out", "r", "href", "l")
DL_EXTS = {"zip", "7z", "rar", "gz", "tgz", "bz2", "xz", "tar", "iso", "img", "exe", "msi", "dmg", "pkg", "deb", "rpm", "apk", "appimage", "pdf", "epub", "mobi",
           "doc", "docx", "xls", "xlsx", "ppt", "pptx", "csv", "mp4", "mkv", "avi", "mov", "webm", "mp3", "flac", "wav", "ogg", "m4a", "torrent"}
_IMG_EXTS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico"}
_DL_WORDS = re.compile(r"download|t[eé]l[eé]charg|descarg|herunterlad|scarica|baixar|direct\s*link|get\s*(?:the\s*)?file", re.I)
_AD_WORDS = re.compile(r"\bads?\b|advert|sponsor|promo|affiliate|casino|\bbet(?:ting)?\b|install\s*now|win\s*a\s", re.I)
_PAYWALL = re.compile(r"subscribe\s+to\s+(?:continue|read|download)|subscribers?\s+only|paywall|members?\s+only|premium\s+members?|(?:sign|log)\s*in\s+to\s+(?:continue|download|view)", re.I)


def _decode_target(v):
    v = (v or "").strip()
    if v.lower().startswith(("http://", "https://")):
        return v
    if v.startswith("aHR0c"):  # base64 of "http"
        try:
            t = base64.urlsafe_b64decode(v + "=" * (-len(v) % 4)).decode("utf-8", "replace")
            return t if t.lower().startswith(("http://", "https://")) else ""
        except (ValueError, TypeError):
            return ""
    t = urllib.parse.unquote(v)
    return t if t.lower().startswith(("http://", "https://")) else ""


def _unwrap_once(url):
    p = urllib.parse.urlparse(url)
    host, qs = (p.hostname or "").lower(), urllib.parse.parse_qs(p.query)
    if host == "href.li" and p.query.lower().startswith("http"):
        return _decode_target(p.query)
    for h, prefix, keys in _WRAPPERS:
        if (host == h or host.endswith("." + h)) and p.path.startswith(prefix):
            for k in keys:
                t = _decode_target((qs.get(k) or [""])[0])
                if t:
                    return t
    if p.path.rstrip("/").rsplit("/", 1)[-1].lower() in _REDIRECTOR_WORDS:  # a path like /redirect, /away.php, /out ...
        for k in _WRAP_KEYS:
            t = _decode_target((qs.get(k) or [""])[0])
            if t:
                return t
    return ""


def unwrap_url(url, max_depth=5):
    """Peel redirect wrappers (google.com/url?q=..., facebook l.php?u=..., /redirect?url=<base64>...) with no network. Returns (url, [each step's address])."""
    steps = []
    for _ in range(max_depth):
        nxt = _unwrap_once(url)
        if not nxt or nxt == url:
            break
        steps.append(nxt)
        url = nxt
    return url, steps


class _AnchorParser(html.parser.HTMLParser):
    """Links with their text, the way a person sees them, plus <meta refresh>."""

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.anchors, self.refresh, self._cur = base, [], "", None

    def _flush(self):
        if self._cur:
            self._cur["text"] = " ".join(self._cur["text"].split())
            self.anchors.append(self._cur)
            self._cur = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "a" and a.get("href", "").strip() and not a["href"].strip().lower().startswith(("javascript:", "mailto:", "tel:", "#", "data:", "blob:")):
            self._flush()
            u = urllib.parse.urldefrag(urllib.parse.urljoin(self.base, a["href"].strip()))[0]
            if u.lower().startswith(("http://", "https://")):
                self._cur = {"url": u, "text": "", "download": "download" in a, "rel": a.get("rel", "").lower(), "cls": (a.get("class", "") + " " + a.get("id", "")).lower()}
        elif tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            m = re.search(r"url\s*=\s*['\"]?([^'\";]+)", a.get("content", ""), re.I)
            if m:
                self.refresh = urllib.parse.urljoin(self.base, m.group(1).strip())

    def handle_data(self, data):
        if self._cur is not None:
            self._cur["text"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self._flush()

    def close(self):
        super().close()
        self._flush()


_JS_REDIRECT = (re.compile(r"""(?:window\.|document\.|top\.|self\.)?location(?:\.href)?\s*=\s*["']([^"'\s]+)["']"""),
                re.compile(r"""location\.(?:replace|assign)\(\s*["']([^"'\s]+)["']\s*\)"""))


def page_links(body, base):
    """(anchors, redirect): the page's links with their text, and where the page itself sends the browser (meta refresh / simple JavaScript), if anywhere."""
    p = _AnchorParser(base)
    try:
        p.feed(body)
        p.close()
    except Exception:
        pass
    redirect = p.refresh
    if not redirect:
        for rx in _JS_REDIRECT:
            m = rx.search(body)
            if m and not m.group(1).startswith(("#", "javascript:")):
                redirect = urllib.parse.urljoin(base, m.group(1))
                break
    return p.anchors, ("" if redirect == base else redirect)


def score_link(a, page_url):
    """How likely a link on a download page is *the* file. Plain rules, no network, nothing sent anywhere."""
    u, text = a["url"], a.get("text", "")
    ext = url_ext(u)
    s = 50 if a.get("download") else 0
    s += 45 if ext in DL_EXTS else 0
    s += 25 if (_DL_WORDS.search(text) or _DL_WORDS.search(a.get("cls", ""))) else 0
    s += 15 if re.search(r"/(?:download|dl|get|files?|attachments?)/|[?&](?:download|dl|export=download)\b", u, re.I) else 0
    s += 10 if urllib.parse.urlparse(u).netloc == urllib.parse.urlparse(page_url).netloc else 0
    s -= 60 if (_AD_WORDS.search(text + " " + a.get("cls", "")) or "sponsored" in a.get("rel", "")) else 0
    s -= 40 if (ext in NOISE_EXTS or ext in _IMG_EXTS) else 0
    s -= 100 if u == page_url else 0
    return s


def default_probe(url):
    """Ask the server about a link without downloading the file: final address, status, type, and (for web pages) the first 512 KB."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    try:
        with OPENER.open(req, timeout=20) as r:
            ctype, disp = r.headers.get("Content-Type") or "", r.headers.get("Content-Disposition") or ""
            body = ""
            if "html" in ctype.lower() and not disp:
                body = r.read(512 * 1024).decode(r.headers.get_content_charset() or "utf-8", "replace")
            return {"url": r.geturl(), "status": getattr(r, "status", 200), "type": ctype, "disp": disp, "size": r.headers.get("Content-Length"), "body": body}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(64 * 1024).decode("utf-8", "replace")
        except OSError:
            body = ""
        return {"url": url, "status": e.code, "type": e.headers.get("Content-Type") or "", "disp": "", "size": None, "body": body}


def _is_file_response(r):
    if re.search(r"attachment|filename", r.get("disp") or "", re.I):
        return True
    return (r.get("type") or "").split(";")[0].strip().lower() not in ("text/html", "application/xhtml+xml")


BLOCKED_NOTE = ("This page asks for a login, subscription or payment before it hands over the file. AeroGrab doesn't get around that. "
                "If you have an account, add the login under Options > Logins, or sign in in your browser and send the link with the AeroGrab extension.")


def resolve_link(url, probe=None, max_hops=6):
    """Find the real file behind a link: peel redirect wrappers, follow shorteners and 'your download will start' pages, and pick the best download
    link on a landing page. It never works around logins or paywalls - those are reported as 'blocked'.
    Returns {'url', 'state', 'note', 'steps', 'candidates'}; state: direct | resolved | choose | blocked | none | failed | skip."""
    probe = probe or default_probe
    start = (url or "").strip()
    res = {"url": start, "state": "failed", "note": "", "steps": [], "candidates": []}
    if not start.lower().startswith(("http://", "https://")):
        res.update(state="skip", note="Only http:// and https:// addresses can be resolved.")
        return res
    cur, wrapped = unwrap_url(normalize_url(start))
    if wrapped:
        res["steps"].append("Removed a redirect wrapper")
    seen = set()
    for _ in range(max_hops):
        if cur in seen:
            break
        seen.add(cur)
        try:
            r = probe(cur)
        except Exception as e:
            res.update(url=cur, state="resolved" if cur != start else "failed", note=f"Couldn't reach the page: {e}")
            return res
        final = unwrap_url(r.get("url") or cur)[0]
        if final != cur:
            res["steps"].append("Followed a redirect")
            cur = final
        code = int(r.get("status") or 200)
        if code in (401, 402, 403):
            res.update(url=cur, state="blocked", note=BLOCKED_NOTE)
            return res
        if code >= 400:
            res.update(url=cur, state="failed", note=f"The server answered HTTP {code}.")
            return res
        if _is_file_response(r):
            res.update(url=cur, state="direct" if cur == start else "resolved", note="Already a direct file link." if cur == start else "Found the file.")
            return res
        anchors, nxt = page_links(r.get("body") or "", cur)
        if nxt and nxt not in seen:
            res["steps"].append("Followed the page's own redirect")
            cur = nxt
            continue
        ranked = sorted(({"url": a["url"], "text": a["text"], "score": score_link(a, cur)} for a in anchors), key=lambda c: -c["score"])
        ranked = [c for i, c in enumerate(ranked) if c["score"] >= 40 and all(c["url"] != x["url"] for x in ranked[:i])]
        if not ranked:
            if _PAYWALL.search(r.get("body") or ""):
                res.update(url=cur, state="blocked", note=BLOCKED_NOTE)
            else:
                res.update(url=cur, state="none", note="No download link found on that page.")
            return res
        if len(ranked) == 1 or ranked[0]["score"] - ranked[1]["score"] >= 25:
            res["steps"].append("Picked the best download link on the page")
            cur = ranked[0]["url"]
            continue
        res.update(url=cur, state="choose", candidates=ranked[:8], note="Several links could be the file - pick one.")
        return res
    res.update(url=cur, state="resolved" if cur != start else "failed", note="Stopped after several steps." if cur != start else "Couldn't find a file.")
    return res


# ---------- clipboard history ----------
CLIP_MAX = 100
_CLIP_URL = re.compile(r"(?:https?|ftps?)://[^\s<>\"']+")


def clip_urls(text):
    """Every http / https / ftp / ftps address in some copied text, in order, without trailing punctuation."""
    return list(dict.fromkeys(u.rstrip(".,;:!?)]}") for u in _CLIP_URL.findall(text or "")))


class ClipHistory:
    """The links the user copied: newest first, no duplicates, kept in clipboard.json (only addresses are stored, never other clipboard text)."""

    def __init__(self, path=None, limit=CLIP_MAX):
        self.path, self.limit, self.items = path, limit, []
        try:
            with open(path) as f:
                rows = json.load(f)
            self.items = [{"url": str(x["url"]), "t": float(x.get("t", 0))} for x in rows if isinstance(x, dict) and str(x.get("url", "")).startswith(URL_SCHEMES)][:limit]
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def add_text(self, text, now=None):
        """Record the links in `text`. Returns the ones that are new (a link copied again just moves to the top)."""
        now, new = time.time() if now is None else now, []
        for u in reversed(clip_urls(text)):
            if not any(x["url"] == u for x in self.items):
                new.append(u)
            self.items = [x for x in self.items if x["url"] != u]
            self.items.insert(0, {"url": u, "t": now})
        del self.items[self.limit:]
        if new:
            self.save()
        return list(reversed(new))

    def remove(self, urls):
        drop = set(urls)
        self.items = [x for x in self.items if x["url"] not in drop]
        self.save()

    def clear(self):
        self.items = []
        self.save()

    def save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.items, f)
        except OSError:
            pass


# ---------- toolbar layout ----------
# every toolbar button AeroGrab knows: id -> (icon, label, App method). The first group is the classic IDM-style set (TOOLBAR, defined later).
EXTRA_TOOLBAR = {"scan": ("scan", "Scan", "scan_selected"), "clip": ("clip", "Clipboard", "clipboard_dialog"), "widget": ("widget", "Widget", "toggle_widget")}
TOOLBAR_STYLES, TOOLBAR_SIZES = ("both", "icons", "text"), ("large", "small")


def toolbar_layout(saved, default, known):
    """The toolbar as a list of button ids, with "|" for a separator. `saved` comes from settings.json, which may have been edited by hand:
    unknown ids and repeats are dropped, separators never double up or sit at the ends, and an empty result falls back to the default."""
    if not isinstance(saved, list):
        return list(default)
    out = []
    for x in saved:
        if x == "|" and out and out[-1] != "|":
            out.append("|")
        elif x in known and x not in out:
            out.append(x)
    while out and out[-1] == "|":
        out.pop()
    return out or list(default)





class Download:
    def __init__(self, url, folder, connections=8, referer=None, cookie=None, ua=None, hint=None):
        url, self.login = split_login(normalize_url(url))  # credentials in the link (ftp://me:pw@host/f) are kept apart from the address
        self.url, self.folder, self.connections = url, folder, connections
        self.referer, self.cookie, self.ua, self.hint = referer, cookie, ua, hint  # cookie is never saved to disk
        self.name = self.path = None
        self.size, self.ranges = -1, False
        self.segs = []  # each: [start, end_or_None, next_byte_pos]
        self.status, self.error = "Queued", ""
        self.speed, self._last = 0.0, (time.time(), 0)
        self.lock = threading.Lock()
        self.limit_kb, self.limiter = 0, Limiter()
        self.base, self.category, self.auto_cat, self.router = folder, "General", True, None  # router: set by the Manager
        self.queue, self.project, self.desc, self.last_try = MAIN_QUEUE, "", "", time.time()
        self.force = self.auto_paused = False  # runtime only
        self.show_complete, self.open_when_done, self.announced = None, False, False  # runtime only; show_complete None = follow the global setting
        self.restart, self.downgraded, self.note = threading.Event(), False, ""  # restart: ask the workers to stop so the transfer can start again as one plain stream
        self.stop = threading.Event()
        self.failed = threading.Event()
        self.thread = None
        self.checksum, self.verified, self.actual_hash, self._verifying = "", "", "", False  # expected 'algo:hex'; '' | 'ok' | 'bad' | 'missing'
        self.scan, self.scan_info, self._scanning, self._scan_t0, self._scan_skip = "", "", False, 0.0, False  # antivirus: '' | 'clean' | 'infected' | 'error' | 'unavailable'
        self.validator, self.replans, self.changed, self._resumed = "", 0, False, False  # ETag / Last-Modified, to notice a file that changed on the server
        self.transient, self.retries, self.retry_at, self._auto_retry = False, 0, 0.0, False  # automatic retry bookkeeping (runtime only)

    # ---------- persistence ----------
    def to_dict(self):
        keys = ("url", "folder", "base", "category", "auto_cat", "queue", "project", "desc", "last_try", "connections", "limit_kb", "referer", "ua", "hint", "name", "path", "size", "ranges", "segs", "status", "error",
                "login", "checksum", "verified", "scan", "scan_info", "validator", "replans")
        d = {k: getattr(self, k) for k in keys}
        d["segs"] = [list(s) for s in self.segs]
        return d

    @classmethod
    def from_dict(cls, d):
        cls = {"hls": HlsDownload, "mux": MuxDownload, "dash": DashDownload, "ytdlp": ExtractDownload, "ytnative": NativeYt, "ftp": FtpDownload}.get(d.get("kind"), cls)
        o = cls(d["url"], d["folder"], d.get("connections", 8))
        for k, v in d.items():
            setattr(o, k, v)
        o.limiter.set_rate(o.limit_kb * 1024)
        o._scan_skip = o.status == "Completed"  # files finished in an earlier session or list are not scanned again behind the user's back
        if o.status in ACTIVE or o.status == "Queued":
            o.status = "Paused"
        getattr(o, "_loaded", lambda: None)()
        o._last = (time.time(), o.done)  # otherwise the first speed reading after a restart is a huge spike
        return o

    # ---------- helpers ----------
    @property
    def done(self):
        return sum((min(s[2], s[1] + 1) if s[1] is not None else s[2]) - s[0] for s in list(self.segs))

    @property
    def percent(self):
        return 100.0 * self.done / self.size if self.size > 0 else 0.0

    def _open(self, headers=None, url=None):
        url = url or self.url
        h = {"User-Agent": self.ua or UA}
        if self.referer:
            h["Referer"] = self.referer
        if self.cookie and urllib.parse.urlparse(url).netloc == urllib.parse.urlparse(self.url).netloc:
            h["Cookie"] = self.cookie  # only ever sent to the host the browser gave us
        if self.login:
            OPENER.add_login(url, *self.login)  # given when the server asks for it (Basic / Digest), and only to this host
        req = urllib.request.Request(url, headers={**h, **(headers or {})})
        return OPENER.open(req, timeout=NET.timeout)

    def _fetch_head(self):
        """First KB of the file (ranged; plain GET if the server rejects Range). A web page is read further, for Google Drive's confirm form."""
        err = None
        for attempt in range(2):
            for rng in (True, False):
                try:
                    with self._open({"Range": "bytes=0-1023"} if rng else None) as r:
                        n = 1 << 19 if "text/html" in (r.headers.get("Content-Type") or "").lower() else 1024
                        return r.status, r.headers, r.geturl(), r.read(n)
                except urllib.error.HTTPError as e:
                    if rng and e.code in (400, 403, 405, 416, 501):
                        err = e
                        continue  # some servers reject Range outright: ask again without it
                    raise
                except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                    err = e
                    break
            time.sleep(1.0)
        raise err

    def _probe(self):
        """Learn size, range support and the real file name: Content-Disposition, redirects, the link itself, then Content-Type and magic bytes."""
        status, hdrs, final, head = self._fetch_head()
        ct = (hdrs.get("Content-Type") or "").split(";")[0].strip().lower()
        if ct == "text/html" and is_drive_host(urllib.parse.urlparse(final).hostname):
            nxt = drive_confirm_url(head.decode("utf-8", "replace"), final)
            if nxt and nxt != self.url:
                self.url = nxt  # Google Drive's "can't scan this file for viruses" step
                status, hdrs, final, head = self._fetch_head()
                ct = (hdrs.get("Content-Type") or "").split(";")[0].strip().lower()
            if ct == "text/html":
                raise IOError("Google Drive refused the download (private file, or its download quota is used up)")
        etag = (hdrs.get("ETag") or "").strip()
        self.validator = etag if etag and not etag.startswith("W/") else (hdrs.get("Last-Modified") or "").strip()  # a weak ETag can't be used with If-Range
        cr = hdrs.get("Content-Range")
        if status == 206 and cr and cr.split("/")[-1].isdigit():
            self.size, self.ranges = int(cr.split("/")[-1]), True
        else:
            cl = hdrs.get("Content-Length")
            self.size, self.ranges = (int(cl) if cl and cl.isdigit() else -1), False
        name, cd = None, hdrs.get("Content-Disposition")
        if cd:
            m = Message()
            m["content-disposition"] = cd
            name = m.get_filename()
        raw = clean_name(self.hint or name or name_from_url(final) or name_from_url(self.url))
        if os.path.splitext(raw)[1].lower().lstrip(".") in BINARY_EXT and looks_like_page(head, ct):
            raise IOError("the server sent a web page instead of the file (the link may have expired, or it needs a login)")
        self.name = clean_name(fix_name(raw, ct, head, f"{self.url} {self.hint or ''}"))

    def _route(self):
        """Pick the category folder now that the real file name is known."""
        if self.router:
            self.router(self)

    def _plan(self):
        self._route()
        os.makedirs(self.folder, exist_ok=True)
        base, ext = os.path.splitext(self.name)
        path, i = os.path.join(self.folder, self.name), 1
        if NET.overwrite and os.path.isfile(path):  # Configuration > Downloads: "replace the existing file"
            try:
                os.remove(path)
            except OSError:
                pass
        while os.path.exists(path):
            path = os.path.join(self.folder, f"{base} ({i}){ext}")
            i += 1
        self.path = path
        self._make_segs()
        self._alloc()

    def _make_segs(self):
        if self.ranges and self.size > 2 * 1024 * 1024:
            n = max(1, self.connections)
            step = -(-self.size // n)
            self.segs = [[i * step, min((i + 1) * step, self.size) - 1, i * step]
                         for i in range(n) if i * step < self.size]
        else:
            self.segs = [[0, self.size - 1 if self.size > 0 else None, 0]]

    def _alloc(self):
        with open(self.path, "wb") as f:
            if self.size > 0:
                f.truncate(self.size)

    def _replan(self):
        """The file changed on the server while we were away: ask again for its size, throw the old pieces away, start over (same file name)."""
        self.replans += 1
        name = self.name
        self._probe()
        self.name, self._resumed, self.note = name, False, ""
        self._make_segs()
        self._alloc()

    def _stale(self):
        """The server answered a resume with the whole file: our partial copy is from an older version of it. True = start over."""
        with self.lock:
            if self.changed:
                return True
            if self.replans >= 1:  # it keeps saying so (e.g. a CDN with a different ETag per server): stop trusting the check
                self.validator = ""
                return False
            self.changed = True
            self.note = "file changed on the server: starting over"
            self.restart.set()
            return True

    def segment_map(self):
        """[(x0, x1, filled_to)] in 0..1: the byte range of every connection's segment and how far it got."""
        if self.size <= 0 or not self.segs:
            return []
        n, out = float(self.size), []
        for x in sorted(list(self.segs), key=lambda z: z[0]):
            end = x[1] if x[1] is not None else self.size - 1
            out.append((x[0] / n, (end + 1) / n, min(max(x[2], x[0]), end + 1) / n))
        return out

    def segment_rows(self):
        """[(n, 'downloaded', 'info')] - one row per connection, for the progress window's N. / Downloaded / Info table."""
        rows, live = [], self.status in ACTIVE
        for i, x in enumerate(sorted(list(self.segs), key=lambda z: z[0]), 1):
            end = x[1]
            got = max(0, (min(x[2], end + 1) if end is not None else x[2]) - x[0])
            if (end is not None and x[2] > end) or self.status == "Completed":
                info = "Complete"
            elif live:
                info = "Receiving data..." if self.status == "Downloading" else "Connecting..."
            else:
                info = "Stopped"
            rows.append((i, human(got), info))
        return rows

    def set_limit(self, kb):
        self.limit_kb = max(0, int(kb))
        self.limiter.set_rate(self.limit_kb * 1024)

    # ---------- checksum ----------
    def set_checksum(self, text):
        """Expected hash ('' clears it). Raises ValueError if it isn't an MD5 / SHA-1 / SHA-256 / SHA-512 value."""
        cs = normalize_checksum(text)
        if cs != self.checksum:
            self.checksum, self.verified, self.actual_hash = cs, "", ""

    def verify(self, stop=None):
        """Hash the finished file and compare it with the expected checksum. Sets .verified to 'ok', 'bad' or 'missing'."""
        cs = parse_checksum(self.checksum)
        if not cs:
            self.verified = ""
            return ""
        self._verifying = True
        try:
            if not self.path or not os.path.isfile(self.path):
                self.verified = "missing"
            else:
                got = hash_file(self.path, cs[0], stop)
                if got is not None:  # None: cancelled
                    self.actual_hash = got
                    self.verified = "ok" if got == cs[1] else "bad"
        except OSError:
            self.verified = "missing"
        finally:
            self._verifying = False
        return self.verified

    def verify_async(self):
        if not self._verifying:
            self._verifying = True  # claimed now, so the scheduler doesn't start a second check
            threading.Thread(target=self.verify, daemon=True).start()

    def scan_async(self, prefer="auto", force=False):
        """Scan the finished file with the installed antivirus, in the background. The verdict lands in .scan / .scan_info."""
        if self._scanning or (self.scan and not force):
            return
        self._scanning, self._scan_t0, self.scan, self.scan_info = True, time.time(), "", ""  # claimed now, so the scheduler doesn't start a second scan
        threading.Thread(target=self._scan, args=(prefer,), daemon=True).start()

    def _scan(self, prefer):
        try:
            res = scan_file(self.path, prefer)
            self.scan_info = av_summary(res)
            self.scan = res["state"]
        except Exception as e:  # never leave the flag stuck
            self.scan_info, self.scan = f"The virus scan didn't finish. {e}", "error"
        finally:
            self._scanning = False

    # ---------- control ----------
    def start(self):
        if self.status in ACTIVE:
            return
        self.stop.clear()
        self.failed.clear()
        self.error, self.transient = "", False
        if self._auto_retry:
            self._auto_retry = False
        else:
            self.retries, self.retry_at = 0, 0.0  # a person pressed Resume: the automatic retries start counting again
        self.last_try = time.time()
        self.status = "Connecting"
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def pause(self):
        self.stop.set()

    def _run(self):
        try:
            self._resumed = bool(self.segs)  # picking up an earlier attempt: ask the server whether the file is still the same one
            if not self.segs:
                self._probe()
                self._plan()
            elif not self.ranges:  # server can't resume: restart from zero
                for x in self.segs:
                    x[2] = x[0]
                open(self.path, "wb").close()
            if not os.path.exists(self.path):
                raise IOError("partial file missing")
            self.status = "Downloading"
            self._last = (time.time(), self.done)
            while True:
                self.restart.clear()
                todo = [x for x in self.segs if x[1] is None or x[2] <= x[1]]
                workers = [threading.Thread(target=self._worker, args=(x,), daemon=True) for x in todo]
                if self.ranges:  # spare connections start idle and steal work from busy ones
                    workers += [threading.Thread(target=self._worker, daemon=True)
                                for _ in range(max(0, self.connections - len(todo)))]
                for w in workers:
                    w.start()
                for w in workers:
                    w.join()
                if self.restart.is_set() and not self.stop.is_set():
                    if self.changed:
                        self.changed = False
                        self._replan()  # the file changed on the server: begin again with its new size
                    else:
                        self._single_stream()  # the server won't do parallel / ranged transfers: carry on as one plain stream
                    continue
                break
            if self.failed.is_set():
                self.status = "Error"
            elif all(x[1] is not None and x[2] > x[1] for x in self.segs):
                if os.path.getsize(self.path) == 0:
                    self.error, self.status = "the server returned an empty file", "Error"
                else:
                    self.status, self.retries = "Completed", 0
            else:
                self.status = "Paused"
        except Exception as e:
            self.error, self.status, self.transient = str(e), "Error", is_transient(e)
        if self.status == "Error" and self.path and self.done == 0:
            self._scrap()
        self.speed = 0

    def _halted(self):
        return self.stop.is_set() or self.failed.is_set() or self.restart.is_set()

    def _downgrade(self, why):
        """Ranged / multi-connection transfer is not working: ask every worker to stop so the file restarts as one plain stream."""
        if self.downgraded or not self.ranges:
            return False
        self.note = "single connection (" + why[:40] + ")"
        self.restart.set()
        return True

    def _single_stream(self):
        self.ranges, self.connections, self.downgraded = False, 1, True
        self.segs = [[0, self.size - 1 if self.size > 0 else None, 0]]
        with open(self.path, "wb") as f:
            if self.size > 0:
                f.truncate(self.size)

    def _scrap(self):
        """Nothing was received: don't leave a zero-filled placeholder behind. The next try plans from scratch."""
        try:
            os.remove(self.path)
        except OSError:
            pass
        self.path, self.segs = None, []

    def _steal(self):
        """Split the largest unfinished segment in two and return the new second half."""
        if not self.ranges:
            return None
        with self.lock:
            best, rem = None, 0
            for x in self.segs:
                if x[1] is not None and x[1] - x[2] + 1 > rem:
                    best, rem = x, x[1] - x[2] + 1
            if best is None or rem < MIN_SPLIT:
                return None
            mid = best[2] + rem // 2
            new = [mid, best[1], mid]
            best[1] = mid - 1  # the victim notices this before its next read
            self.segs.append(new)
            return new

    def _worker(self, seg=None):
        while not self._halted():
            if seg is None or (seg[1] is not None and seg[2] > seg[1]):
                seg = self._steal()
                if seg is None:
                    return
            self._fetch(seg)
            if seg[1] is None:
                return

    def _fetch(self, seg):
        tries = 0
        while not self._halted():
            end = seg[1]
            if end is not None and seg[2] > end:
                return
            try:
                hdr = {}
                if self.ranges:
                    hdr["Range"] = f"bytes={seg[2]}-{'' if end is None else end}"
                    if self._resumed and self.validator:
                        hdr["If-Range"] = self.validator  # "only if the file is still the one I started with"
                with self._open(hdr) as r, open(self.path, "r+b") as f:
                    if self.ranges and r.status != 206:
                        if "If-Range" in hdr and r.status == 200:
                            if self._stale():
                                return
                            raise IOError("the file changed on the server; trying again without the check")
                        if self._downgrade("server ignored Range"):
                            return
                        raise IOError("server ignored Range request")
                    f.seek(seg[2])
                    while not self._halted():
                        end = seg[1]  # may shrink when another connection steals our tail
                        ck = _chunk_for(GLOBAL_LIMIT, self.limiter)
                        want = ck if end is None else min(ck, end - seg[2] + 1)
                        if want <= 0:
                            return
                        buf = r.read(want)
                        if not buf:
                            if end is None:  # unknown length: EOF means finished
                                seg[1] = seg[2] - 1
                                return
                            raise IOError("connection closed early")
                        f.write(buf)
                        seg[2] += len(buf)
                        tries = 0
                        GLOBAL_LIMIT.wait(len(buf), self.stop)
                        self.limiter.wait(len(buf), self.stop)
            except Exception as e:
                code = getattr(e, "code", None)
                if self.ranges and code in (400, 403, 405, 416, 429, 501) and self._downgrade(f"HTTP {code}"):
                    return
                tries = 99 if code in (401, 403, 404, 410) else tries + 1  # permanent refusals aren't worth retrying
                if tries > NET.retries:
                    if self._downgrade(str(e)):
                        return
                    self.error, self.transient = str(e), is_transient(e)
                    self.failed.set()
                    return
                if not self.ranges:
                    seg[2] = seg[0]  # a plain stream can't resume mid-file: begin again
                if self.stop.wait(max(min(2 * tries, 15), retry_after(e))):  # a Retry-After from the server wins; Pause interrupts the wait
                    return

    def update_speed(self):
        now, d = time.time(), self.done
        t0, d0 = self._last
        if now - t0 >= 1:
            self.speed = max(0, (d - d0) / (now - t0))
            self._last = (now, d)

    @property
    def label(self):
        """What the File Name column shows: the real name once known, else a guess from the address (like IDM)."""
        if self.name:
            return self.name
        guess = self.hint or urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(self.url).path))
        return clean_name(guess) if guess else self.url

    @property
    def eta_sec(self):
        if self.status != "Downloading" or self.speed <= 0 or self.size <= 0:
            return None
        return max(0.0, (self.size - self.done) / self.speed)

    @property
    def eta(self):
        if self.status != "Downloading" or self.speed <= 0 or self.size <= 0:
            return ""
        s = int((self.size - self.done) / self.speed)
        return f"{s // 3600:d}:{s % 3600 // 60:02d}:{s % 60:02d}"


class _Halt(Exception):
    """Raised inside an FTP data callback to stop the transfer (pause / failure elsewhere)."""


class FtpDownload(Download):
    """ftp:// and ftps:// (explicit TLS): one connection, resumes with REST, user name / password from the link or from Options > Logins."""
    kind = "ftp"

    def __init__(self, url, folder, connections=1, **kw):
        super().__init__(url, folder, 1, **kw)
        self.connections = 1

    def to_dict(self):
        d = super().to_dict()
        d.update(kind="ftp")
        return d

    def _creds(self, host):
        if self.login:
            return self.login[0], self.login[1]
        got = OPENER.login_for(host)
        return got if got else ("anonymous", "anonymous@")

    def _ftp_connect(self):
        p = urllib.parse.urlsplit(self.url)
        ftp = (ftplib.FTP_TLS if p.scheme == "ftps" else ftplib.FTP)()
        ftp.encoding = "utf-8"
        ftp.connect(p.hostname, p.port or 21, timeout=30)
        try:
            ftp.login(*self._creds(p.hostname))
            if p.scheme == "ftps":
                ftp.prot_p()
            ftp.voidcmd("TYPE I")
        except BaseException:
            ftp.close()
            raise
        return ftp, urllib.parse.unquote(p.path) or "/"

    @staticmethod
    def _bye(ftp):
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    def _probe(self):
        ftp, path = self._ftp_connect()
        try:
            try:
                size = ftp.size(path)
            except ftplib.error_perm:
                size = None
            if size is None:  # no SIZE support, or a folder: a folder can be entered, a file can't
                try:
                    ftp.cwd(path)
                except ftplib.error_perm:
                    pass
                else:
                    raise IOError("that FTP address is a folder, not a file")
            self.size = size if size is not None else -1
            try:
                ftp.sendcmd("REST 0")
                self.ranges = self.size > 0
            except ftplib.error_perm:
                self.ranges = False
        finally:
            self._bye(ftp)
        name = clean_name(self.hint or urllib.parse.unquote(os.path.basename(path.rstrip("/"))) or urllib.parse.urlsplit(self.url).hostname or "file")
        self.name = name

    def _fetch(self, seg):
        tries = 0
        while not self._halted():
            end = seg[1]
            if end is not None and seg[2] > end:
                return
            ftp = None
            try:
                ftp, path = self._ftp_connect()
                with open(self.path, "r+b") as f:
                    f.seek(seg[2])

                    def sink(buf):
                        nonlocal tries
                        if self._halted():
                            raise _Halt()
                        f.write(buf)
                        seg[2] += len(buf)
                        tries = 0
                        GLOBAL_LIMIT.wait(len(buf), self.stop)
                        self.limiter.wait(len(buf), self.stop)
                    ftp.retrbinary("RETR " + path, sink, blocksize=CHUNK, rest=seg[2] if seg[2] > 0 and self.ranges else None)
                if seg[1] is None:
                    seg[1] = seg[2] - 1  # unknown length: the end of the transfer is the end of the file
                elif seg[2] <= seg[1]:
                    raise IOError("connection closed early")
                return
            except _Halt:
                return
            except Exception as e:
                tries = 99 if isinstance(e, ftplib.error_perm) else tries + 1  # 530 (login) / 550 (no such file) won't change by asking again
                if tries > NET.retries:
                    self.error, self.transient = str(e), is_transient(e)
                    self.failed.set()
                    return
                if not self.ranges:
                    seg[2] = seg[0]
                if self.stop.wait(min(2 * tries, 15)):
                    return
            finally:
                if ftp is not None:
                    try:
                        ftp.close()
                    except Exception:
                        pass


# ============================ HLS video downloads ============================
class Fatal(Exception):
    """An error that retrying cannot fix."""


def parse_attrs(s):
    return {k: v.strip('"') for k, v in re.findall(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', s)}


def aes_decrypt(data, key, iv):
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        out = dec.update(data) + dec.finalize()
    except ImportError:
        try:
            from Crypto.Cipher import AES
            out = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except ImportError:
            raise Fatal("This stream is AES-encrypted. Install a decryption library:  pip install cryptography")
    pad = out[-1] if out else 0
    return out[:-pad] if 1 <= pad <= 16 and out.endswith(bytes([pad]) * pad) else out


class HlsDownload(Download):
    """HLS (.m3u8) on-demand streams: parallel segments, AES-128, resume, ffmpeg mux/remux if installed.
    Live streams and DRM (SAMPLE-AES, Widevine, FairPlay) are not supported."""
    kind = "hls"

    def __init__(self, url, folder, connections=8, quality=0, pick_bw=0, **kw):
        super().__init__(url, folder, connections, **kw)
        self.pick_bw = pick_bw  # exact variant bitrate chosen in the browser (0 = just use the height cap)
        self.quality, self.total, self.segs_done, self.bytes_done, self.note = quality, 0, 0, 0, ""
        self.plan, self._keys = None, {}
        self.flags, self._off = bytearray(), {}  # one byte per segment: 1 = downloaded (for the segment map)

    def to_dict(self):
        d = super().to_dict()
        d.update(kind="hls", quality=self.quality, pick_bw=self.pick_bw, total=self.total, segs_done=self.segs_done,
                 bytes_done=self.bytes_done, note=self.note)
        return d

    @property
    def done(self):
        return self.bytes_done

    @property
    def percent(self):
        return 100.0 * self.segs_done / self.total if self.total else 0.0

    def discard(self):
        if self.path:
            shutil.rmtree(parts_dir(self.path), ignore_errors=True)

    def segment_map(self):
        f, out, i = self.flags, [], 0
        n = len(f)
        while i < n:
            j = i
            while j < n and f[j] == f[i]:
                j += 1
            out.append((i / n, j / n, j / n if f[i] else i / n))
            i = j
        return out

    def segment_rows(self):
        if self.status == "Completed":
            info = "Complete"
        elif self.status in ACTIVE:
            info = f"{self.segs_done}/{self.total} parts"
        else:
            info = f"Stopped ({self.segs_done}/{self.total} parts)"
        return [(1, human(self.bytes_done), info)]

    def _open(self, headers=None, url=None):
        h = dict(headers or {})
        if self.referer:
            p = urllib.parse.urlparse(self.referer)
            h.setdefault("Origin", f"{p.scheme}://{p.netloc}")
        return super()._open(h, url)

    # ---------- playlist parsing ----------
    def _text(self, url):
        with self._open(url=url) as r:
            return r.read(8 << 20).decode("utf-8", "replace"), r.geturl()

    def _choose(self, text, base):
        """Master playlist -> (video playlist url, separate audio playlist url or None)."""
        lines, variants, audio = text.splitlines(), [], []
        for i, l in enumerate(lines):
            if l.startswith("#EXT-X-STREAM-INF:"):
                a = parse_attrs(l.split(":", 1)[1])
                uri = next((x for x in lines[i + 1:] if x.strip() and not x.startswith("#")), None)
                if uri:
                    res = a.get("RESOLUTION", "")
                    variants.append({"bw": int(a.get("BANDWIDTH", 0) or 0), "aud": a.get("AUDIO"),
                                     "h": int(res.split("x")[1]) if "x" in res else 0,
                                     "u": urllib.parse.urljoin(base, uri.strip())})
            elif l.startswith("#EXT-X-MEDIA:"):
                a = parse_attrs(l.split(":", 1)[1])
                if a.get("TYPE") == "AUDIO" and a.get("URI"):
                    audio.append(dict(a, URI=urllib.parse.urljoin(base, a["URI"])))
        if not variants:
            raise Fatal("No playable variants in the playlist")
        q = self.quality
        pool = [v for v in variants if q <= 0 or 0 < v["h"] <= q]
        if not pool:
            pool = [min(variants, key=lambda v: (v["h"], v["bw"]))]
        best = max(pool, key=lambda v: (v["h"], v["bw"]))
        exact = [v for v in pool if self.pick_bw and v["bw"] == self.pick_bw]
        if exact:  # the user picked this exact rendition in the browser
            best = max(exact, key=lambda v: v["h"])
        aud = None
        if best["aud"]:
            grp = [a for a in audio if a.get("GROUP-ID") == best["aud"]]
            if grp:
                aud = next((a for a in grp if a.get("DEFAULT") == "YES"), grp[0])["URI"]
        return best["u"], aud

    @staticmethod
    def _br(spec, url, last_end):
        if not spec:
            return None
        n, _, o = spec.partition("@")
        start = int(o) if o else last_end.get(url, 0)
        last_end[url] = start + int(n)
        return f"{int(n)}@{start}"

    def _parse_media(self, text, base):
        if "#EXT-X-ENDLIST" not in text:
            raise Fatal("Live streams are not supported")
        m = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", text)
        seq, key, parts, last_end, pending = (int(m.group(1)) if m else 0), None, [], {}, None
        for l in (x.strip() for x in text.splitlines()):
            if l.startswith("#EXT-X-KEY:"):
                a = parse_attrs(l.split(":", 1)[1])
                meth = a.get("METHOD", "NONE")
                if meth == "NONE":
                    key = None
                elif meth == "AES-128" and a.get("URI"):
                    key = {"u": urllib.parse.urljoin(base, a["URI"]), "iv": a.get("IV")}
                else:
                    raise Fatal(f"Unsupported encryption ({meth}). DRM-protected streams can't be downloaded")
            elif l.startswith("#EXT-X-MAP:"):
                a = parse_attrs(l.split(":", 1)[1])
                u = urllib.parse.urljoin(base, a["URI"])
                parts.append({"u": u, "br": self._br(a.get("BYTERANGE"), u, last_end), "key": None, "init": True})
            elif l.startswith("#EXT-X-BYTERANGE:"):
                pending = l.split(":", 1)[1]
            elif l and not l.startswith("#"):
                u = urllib.parse.urljoin(base, l)
                parts.append({"u": u, "br": self._br(pending, u, last_end), "key": key, "seq": seq})
                seq, pending = seq + 1, None
        if not parts:
            raise Fatal("The playlist has no segments")
        return parts

    def _plan_hls(self):
        text, base = self._text(self.url)
        sources = [("v", text, base)]
        if "#EXT-X-STREAM-INF" in text:
            vu, au = self._choose(text, base)
            sources = [("v",) + self._text(vu)]
            if au:
                sources.append(("a",) + self._text(au))
        tracks = [{"name": n, "parts": self._parse_media(t, b)} for n, t, b in sources]
        ext = ".mp4" if any(p.get("init") for p in tracks[0]["parts"]) else ".ts"
        stem = self.hint or urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(self.url).path))
        stem = clean_name(re.sub(r"\.(m3u8?|mp4|ts|mkv|webm)$", "", stem, flags=re.I))
        if stem.lower() in ("index", "playlist", "master", "manifest", "chunklist", "download"):
            stem = clean_name(urllib.parse.urlparse(self.url).netloc + " video")
        self.name = stem + ext
        self._route()
        os.makedirs(self.folder, exist_ok=True)
        n, name = 0, stem
        while any(os.path.exists(os.path.join(self.folder, name + e)) for e in (ext, ".mp4", ext + ".parts")):
            n += 1
            name = f"{stem} ({n})"
        self.name, self.path = name + ext, os.path.join(self.folder, name + ext)
        os.makedirs(parts_dir(self.path), exist_ok=True)
        self.plan = {"tracks": tracks}
        with open(os.path.join(parts_dir(self.path), "plan.json"), "w") as f:
            json.dump(self.plan, f)

    def _fn(self, track, i):
        return os.path.join(parts_dir(self.path), f"{track['name']}_{i:06d}.part")

    # ---------- downloading ----------
    def _get(self, url, br=None):
        hdr = {}
        if br:
            n, _, o = br.partition("@")
            hdr["Range"] = f"bytes={int(o)}-{int(o) + int(n) - 1}"
        chunks = []
        with self._open(hdr, url) as r:
            while not self.stop.is_set():
                b = r.read(_chunk_for(GLOBAL_LIMIT, self.limiter))
                if not b:
                    return b"".join(chunks)
                chunks.append(b)
                with self.lock:
                    self.bytes_done += len(b)
                GLOBAL_LIMIT.wait(len(b), self.stop)
                self.limiter.wait(len(b), self.stop)
        return None  # stopped

    def _key(self, url):
        with self.lock:
            k = self._keys.get(url)
        if k is None:
            k = self._get(url)
            if k is None:
                return None
            if len(k) != 16:
                raise Fatal("The encryption key could not be fetched (login or referer required?)")
            with self.lock:
                self._keys[url] = k
        return k

    def _hls_worker(self, todo):
        while not self.stop.is_set() and not self.failed.is_set():
            with self.lock:
                job = next(todo, None)
            if job is None:
                return
            t, i = job
            p, fn = t["parts"][i], self._fn(t, i)
            tries_max = max(1, NET.retries - 2)
            for attempt in range(tries_max):
                try:
                    data = self._get(p["u"], p.get("br"))
                    if data is None:
                        return
                    if p.get("key"):
                        kb = self._key(p["key"]["u"])
                        if kb is None:
                            return
                        iv = int(p["key"]["iv"], 16).to_bytes(16, "big") if p["key"].get("iv") else p["seq"].to_bytes(16, "big")
                        data = aes_decrypt(data, kb, iv)
                    with open(fn + ".tmp", "wb") as f:
                        f.write(data)
                    os.replace(fn + ".tmp", fn)
                    with self.lock:
                        self.segs_done += 1
                        self.flags[self._off[t["name"]] + i] = 1
                        self.size = int(self.bytes_done / self.segs_done * self.total)
                    break
                except Fatal as e:
                    self.error = str(e)
                    self.failed.set()
                    return
                except Exception as e:
                    if attempt == tries_max - 1:
                        self.error, self.transient = f"segment {i + 1}: {e}", is_transient(e)
                        self.failed.set()
                        return
                    if self.stop.wait(1 + attempt * 2):
                        return

    def _run(self):
        try:
            pf = os.path.join(parts_dir(self.path), "plan.json") if self.path else None
            if pf and os.path.exists(pf):
                with open(pf) as f:
                    self.plan = json.load(f)
            else:
                self._plan_hls()
            tracks = self.plan["tracks"]
            self.total = sum(len(t["parts"]) for t in tracks)
            self.segs_done = self.bytes_done = 0
            self.flags, self._off, off = bytearray(self.total), {}, 0
            for t in tracks:
                self._off[t["name"]] = off
                for i in range(len(t["parts"])):
                    if os.path.exists(self._fn(t, i)):
                        self.segs_done += 1
                        self.flags[off + i] = 1
                        self.bytes_done += os.path.getsize(self._fn(t, i))
                off += len(t["parts"])
            self.status, self.note = "Downloading", ""
            self._last = (time.time(), self.done)
            todo = iter([(t, i) for t in tracks for i in range(len(t["parts"])) if not os.path.exists(self._fn(t, i))])
            workers = [threading.Thread(target=self._hls_worker, args=(todo,), daemon=True)
                       for _ in range(max(1, self.connections))]
            for w in workers:
                w.start()
            for w in workers:
                w.join()
            if self.failed.is_set():
                self.status = "Error"
            elif all(os.path.exists(self._fn(t, i)) for t in tracks for i in range(len(t["parts"]))):
                self.note = "merging..."
                self.note = self._finish()
                self.status = "Completed"
            else:
                self.status = "Paused"
        except Fatal as e:
            self.error, self.status = str(e), "Error"
        except Exception as e:
            self.error, self.status = str(e), "Error"
        self.speed = 0

    def _finish(self):
        pd = parts_dir(self.path)
        base, ext = os.path.splitext(self.path)
        outs = []
        for t in self.plan["tracks"]:
            out = os.path.join(pd, t["name"] + ".merged")
            with open(out, "wb") as o:
                for i in range(len(t["parts"])):
                    with open(self._fn(t, i), "rb") as f:
                        shutil.copyfileobj(f, o, 1 << 20)
            outs.append(out)
        ff, note, final = find_ffmpeg(), "", self.path
        merged = merge_streams(ff, outs, base) if ff and (len(outs) == 2 or ext == ".ts") else None
        if merged:
            final = merged
        elif len(outs) == 2:  # separate video + audio renditions, and no way to merge them
            shutil.move(outs[0], self.path)
            shutil.move(outs[1], base + ".audio" + ext)
            note = "audio saved as a separate file (install ffmpeg to merge)"
        else:
            shutil.move(outs[0], self.path)
        self.path, self.name = final, os.path.basename(final)
        shutil.rmtree(pd, ignore_errors=True)
        return note


class MuxDownload(Download):
    """A silent video file + a separate audio file (how Facebook, Instagram and other DASH sites serve video).
    Both download in parallel into a temp folder, then are merged into one .mp4 with ffmpeg
    (without ffmpeg they are kept side by side, so nothing is lost)."""
    kind = "mux"

    def __init__(self, url, folder, connections=8, audio_url="", **kw):
        super().__init__(url, folder, connections, **kw)
        self.audio_url, self.note = audio_url, ""
        tmp = os.path.join(folder, ".aerograb-" + secrets.token_hex(4))
        common = dict(referer=self.referer, cookie=self.cookie, ua=self.ua)
        self.children = [Download(url, tmp, connections, hint="video.mp4", **common),
                         Download(audio_url, tmp, max(2, connections // 2), hint="audio.m4a", **common)]
        if self.hint:
            self.name = clean_name(re.sub(r"\.(mp4|m4a|m4v|webm|mkv)$", "", self.hint, flags=re.I)) + ".mp4"

    def to_dict(self):
        d = super().to_dict()
        d.update(kind="mux", audio_url=self.audio_url, note=self.note, children=[c.to_dict() for c in self.children])
        return d

    def _loaded(self):
        self.children = [Download.from_dict(c) if isinstance(c, dict) else c for c in self.children]

    @property
    def done(self):
        return sum(c.done for c in self.children)

    def _sync(self):
        sizes = [c.size for c in self.children]
        self.size = sum(sizes) if all(z > 0 for z in sizes) else -1

    def set_limit(self, kb):
        super().set_limit(kb)
        for c in self.children:
            c.set_limit(kb)

    def pause(self):
        super().pause()
        for c in self.children:
            c.pause()

    def discard(self):
        if self.status != "Completed":
            shutil.rmtree(self.children[0].folder, ignore_errors=True)

    def segment_rows(self):
        out = []
        for label, c in zip(("Video", "Audio"), self.children):
            for _, got, info in c.segment_rows():
                out.append((len(out) + 1, got, f"{label}: {info}"))
        return out

    def segment_map(self):
        sizes = [max(c.size, 0) for c in self.children]
        total, out, off = sum(sizes), [], 0.0
        for c, z in zip(self.children, sizes):
            for x0, x1, xf in (c.segment_map() if total else []):
                out.append((off + x0 * z / total, off + x1 * z / total, off + xf * z / total))
            off += z / total if total else 0
        return out

    def _join_children(self):
        for c in self.children:
            if c.thread:
                c.thread.join(timeout=10)

    def _run(self):
        try:
            self.note = ""
            for c in self.children:
                if c.status != "Completed":
                    c.start()
            self.status = "Downloading"
            self._last = (time.time(), self.done)
            while not self.stop.is_set():
                self._sync()
                bad = next((c for c in self.children if c.status == "Error"), None)
                if bad or all(c.status == "Completed" for c in self.children):
                    if bad:
                        self.error = bad.error or "download failed"
                        for c in self.children:
                            c.pause()
                    break
                time.sleep(0.2)
            self._join_children()
            self._sync()
            if any(c.status == "Error" for c in self.children):
                self.status = "Error"
            elif all(c.status == "Completed" for c in self.children):
                self.note = "merging..."
                self.note = self._merge()
                self.status = "Completed"
            else:
                self.status = "Paused"
        except Exception as e:
            self.error, self.status = str(e), "Error"
        self.speed = 0

    def _merge(self):
        v, a = self.children
        stem = clean_name(re.sub(r"\.(mp4|m4a|m4v|webm|mkv)$", "", self.hint or v.name or "video", flags=re.I))
        self.name = stem + ".mp4"
        self._route()
        os.makedirs(self.folder, exist_ok=True)
        n, name = 0, stem
        while any(os.path.exists(os.path.join(self.folder, name + e)) for e in (".mp4", ".mkv", " (video only).mp4", " (audio only).m4a")):
            n += 1
            name = f"{stem} ({n})"
        ff, note = find_ffmpeg(), ""
        merged = merge_streams(ff, [v.path, a.path], os.path.join(self.folder, name), maps=True) if ff else None
        if merged:
            self.path = merged
        else:
            self.path = os.path.join(self.folder, name + " (video only).mp4")
            shutil.move(v.path, self.path)
            shutil.move(a.path, os.path.join(self.folder, name + " (audio only).m4a"))
            note = ("ffmpeg not found" if not ff else "merge failed") + ": saved video and audio as separate files"
        self.name = os.path.basename(self.path)
        shutil.rmtree(v.folder, ignore_errors=True)
        return note


class DashDownload(Download):
    """MPEG-DASH (.mpd): ffmpeg reads the manifest, fetches every segment and writes one clean .mp4 (or .mkv when MP4 can't hold the codecs)."""
    kind = "dash"

    def __init__(self, url, folder, connections=8, quality=0, **kw):
        super().__init__(url, folder, connections, **kw)
        self.quality, self.note, self.bytes_done, self.out_us, self.dur_us = quality, "", 0, 0, 0

    def to_dict(self):
        d = super().to_dict()
        d.update(kind="dash", quality=self.quality, note=self.note)
        return d

    @property
    def done(self):
        return self.bytes_done

    @property
    def percent(self):
        if self.status == "Completed":
            return 100.0
        return min(99.9, 100.0 * self.out_us / self.dur_us) if self.dur_us else 0.0

    def segment_map(self):
        return []

    def segment_rows(self):
        return [(1, human(self.bytes_done), "Complete" if self.status == "Completed" else "Receiving data..." if self.status in ACTIVE else "Stopped")]

    def _manifest(self):
        with self._open() as r:
            text = r.read(4_000_000).decode("utf-8", "replace")
        if "<MPD" not in text:
            raise IOError("this address is not a DASH manifest")
        if re.search(r"<ContentProtection[^>]+(widevine|playready|edef8ba9|9a04f079)", text, re.I):
            raise IOError("this stream is DRM-protected (Widevine/PlayReady) and can't be downloaded")
        m = re.search(r'mediaPresentationDuration="PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?"', text)
        if m:
            h, mi, s = (float(x or 0) for x in m.groups())
            self.dur_us = int((h * 3600 + mi * 60 + s) * 1e6)

    def _run(self):
        proc = None
        try:
            self.note, self.bytes_done, self.out_us = "", 0, 0
            ff = find_ffmpeg()
            if not ff:
                raise IOError("ffmpeg is needed for DASH (.mpd) streams: put ffmpeg next to aerograb.py, or set AEROGRAB_FFMPEG")
            self._manifest()
            stem = os.path.splitext(clean_name(self.hint or name_from_url(self.url) or "video"))[0]
            if not self.path:
                self.name = stem + ".mp4"
                self._route()
                os.makedirs(self.folder, exist_ok=True)
                n, base = 0, stem
                while any(os.path.exists(os.path.join(self.folder, base + e)) for e in (".mp4", ".mkv")):
                    n += 1
                    base = f"{stem} ({n})"
                self.path = os.path.join(self.folder, base + ".mp4")
            base = os.path.splitext(self.path)[0]
            hdr = f"User-Agent: {self.ua or UA}\r\n" + (f"Referer: {self.referer}\r\n" if self.referer else "") + (f"Cookie: {self.cookie}\r\n" if self.cookie else "")
            self.status, err = "Downloading", ""
            self._last = (time.time(), 0)
            for ext, codec in ((".mp4", ["-c", "copy", "-movflags", "+faststart"]), (".mkv", ["-c", "copy"])):
                tmp = base + ".aerograb-part" + ext
                proc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1", *OPENER.ffmpeg_proxy_args(), "-headers", hdr, "-i", self.url, *codec, tmp],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace", **_ff_flags())
                errs = []
                threading.Thread(target=lambda p=proc, e=errs: e.extend(p.stderr.read().splitlines()), daemon=True).start()
                threading.Thread(target=self._watch, args=(proc,), daemon=True).start()
                for line in proc.stdout:
                    k, _, v = line.strip().partition("=")
                    if k in ("out_time_us", "out_time_ms") and v.lstrip("-").isdigit():
                        self.out_us = max(self.out_us, int(v))
                    elif k == "total_size" and v.isdigit():
                        self.bytes_done = int(v)
                rc = proc.wait()
                if self.stop.is_set():
                    self._rm(tmp)
                    self.status, self.speed = "Paused", 0
                    return
                if rc == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
                    final = base + ext
                    self._rm(final)
                    os.replace(tmp, final)
                    self.path, self.name, self.bytes_done = final, os.path.basename(final), os.path.getsize(final)
                    self.size, self.status = self.bytes_done, "Completed"
                    self.speed = 0
                    return
                self._rm(tmp)
                err = " ".join(errs[-2:])[:200]
            raise IOError("ffmpeg could not download this stream" + (f": {err}" if err else ""))
        except Exception as e:
            self.error, self.status = str(e), "Error"
        self.speed = 0

    def _watch(self, proc):
        if self._wait_stop(proc):
            proc.terminate()

    def _wait_stop(self, proc):
        while proc.poll() is None:
            if self.stop.wait(0.3):
                return True
        return False

    @staticmethod
    def _rm(p):
        try:
            os.remove(p)
        except OSError:
            pass


class NativeYt(Download):
    """yt-dlp's own downloader, for streams AeroGrab's engine can't fetch directly (fragmented DASH and the like)."""
    kind = "ytnative"

    def __init__(self, url, folder, connections=8, quality=0, **kw):
        super().__init__(url, folder, connections, **kw)
        self.quality = quality

    def to_dict(self):
        d = super().to_dict()
        d.update(kind="ytnative", quality=self.quality)
        return d

    def _run(self):
        try:
            y = _ytdlp()
            if y is None:
                raise IOError(YT_MISSING)
            os.makedirs(self.folder, exist_ok=True)
            if self.hint:
                stem = os.path.splitext(clean_name(self.hint))[0] or "video"
                n, base = 0, stem
                while any(os.path.exists(os.path.join(self.folder, base + e)) for e in (".mp4", ".mkv", ".webm", ".m4a")):
                    n += 1
                    base = f"{stem} ({n})"
                tmpl = base.replace("%", "%%")  # a '%' in a title must not be read as a template field
            else:  # nothing known about the video yet (a link typed into AeroGrab): name it the way yt-dlp does
                base, tmpl = "", "%(title).120B [%(id)s]"
            self.status = "Downloading"
            files = {}  # file name -> [bytes so far, bytes expected]: video and audio are two files, the bar covers both

            def hook(h):
                if self.stop.is_set():
                    raise IOError("stopped")
                st = h.get("status")
                if st in ("downloading", "finished"):
                    fn = h.get("filename") or h.get("tmpfilename") or ""
                    got = int(h.get("downloaded_bytes") or 0)
                    tot = int(h.get("total_bytes") or h.get("total_bytes_estimate") or 0)
                    files[fn] = [got, max(got, got if st == "finished" else tot)]
                    done, total = sum(v[0] for v in files.values()), sum(v[1] for v in files.values())
                    self.size = total if total > 0 else -1
                    self.segs = [[0, total - 1 if total > 0 else None, done]]

            def post(h):
                if self.stop.is_set():
                    raise IOError("stopped")
                self.note = "joining video and audio..." if h.get("status") == "started" else ""
            opts = dict(ytdlp_opts(self.quality, self.referer, self.cookie, self.ua, self.limit_kb), outtmpl=os.path.join(self.folder, tmpl + ".%(ext)s"), windowsfilenames=os.name == "nt",
                        progress_hooks=[hook], postprocessor_hooks=[post], noprogress=True)
            with y.YoutubeDL(opts) as ydl:
                apply_cookies(ydl, self.cookie, self.url)  # FIX: cookies via cookiejar
                info = ydl.extract_info(self.url, download=True)
                if info and info.get("entries"):
                    info = next((e for e in info["entries"] if e), None)
                path = ((info or {}).get("requested_downloads") or [{}])[0].get("filepath") or (ydl.prepare_filename(info) if info else "")
            if base and (not path or not os.path.isfile(path)):
                path = next((os.path.join(self.folder, f) for f in sorted(os.listdir(self.folder)) if f.startswith(base + ".") and not f.endswith((".part", ".ytdl"))), "")
            if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
                raise IOError("yt-dlp finished but no file was written")
            self.path, self.name, self.size = path, os.path.basename(path), os.path.getsize(path)
            self.segs, self.status = [[0, self.size - 1, self.size]], "Completed"
        except Exception as e:
            if self.stop.is_set():
                self.status = "Paused"
            else:
                code, hint = explain_ytdlp_error(e)
                self.error, self.status = (hint + "  [" + re.sub(r"\s+", " ", str(e))[:140] + "]") if hint else str(e), "Error"
                self.transient = code in ("network",)
        self.speed = 0


class ExtractDownload(Download):
    """A video page (YouTube, Facebook, Instagram, Vimeo, TikTok ...): yt-dlp finds the real stream links, AeroGrab's own engine downloads
    them (multi-connection, resumable) and ffmpeg merges video + audio into one file."""
    kind = "ytdlp"

    def __init__(self, url, folder, connections=8, quality=0, **kw):
        super().__init__(url, folder, connections, **kw)
        self.quality, self.note, self.title, self.inner = quality, "", "", None
        self._native_first = False  # runtime only: AeroGrab's own engine failed once, let yt-dlp's downloader do the whole job

    def to_dict(self):
        d = super().to_dict()
        d.update(kind="ytdlp", quality=self.quality, note=self.note, title=self.title, inner=self.inner.to_dict() if self.inner else None)
        return d

    def _loaded(self):
        if isinstance(self.inner, dict):
            self.inner = Download.from_dict(self.inner)

    @property
    def label(self):
        return self.name or self.hint or self.title or self.url

    @property
    def done(self):
        return self.inner.done if self.inner else 0

    @property
    def percent(self):
        return self.inner.percent if self.inner else 0.0

    def segment_map(self):
        return self.inner.segment_map() if self.inner else []

    def segment_rows(self):
        return self.inner.segment_rows() if self.inner else []

    def set_limit(self, kb):
        super().set_limit(kb)
        if self.inner:
            self.inner.set_limit(kb)

    def pause(self):
        super().pause()
        if self.inner:
            self.inner.pause()

    def discard(self):
        self._drop_inner()

    def _drop_inner(self):
        i, self.inner = self.inner, None
        if not i:
            return
        if hasattr(i, "discard"):
            i.discard()
        if i.status != "Completed" and i.path and os.path.exists(i.path):
            try:
                os.remove(i.path)
            except OSError:
                pass

    def _sync(self):
        i = self.inner
        if i:
            self.size, self.ranges = i.size, i.ranges
            if i.name:
                self.name = i.name
            if i.path:
                self.path = i.path
            self.note = i.note if getattr(i, "note", "") else self.note

    def _build(self, plan):
        self.title = plan["title"]
        ext = os.path.splitext(plan["name"])[1]
        h = clean_name(self.hint) if self.hint else ""
        self.name = h if h and os.path.splitext(h)[1].lower().lstrip(".") in BINARY_EXT else (h + ext if h else plan["name"])
        self._route()  # category folder, now that the real name is known
        common = dict(referer=plan.get("referer") or self.referer, cookie=self.cookie, ua=plan.get("ua") or self.ua)
        k, c = plan["kind"], self.connections
        if k == "direct":
            inner = Download(plan["url"], self.folder, c, hint=self.name, **common)
        elif k == "mux":
            inner = MuxDownload(plan["url"], self.folder, c, audio_url=plan["audio"], hint=self.name, **common)
        elif k == "hls":
            inner = HlsDownload(plan["url"], self.folder, c, quality=self.quality, hint=self.name, **common)
        else:
            inner = NativeYt(self.url, self.folder, c, quality=self.quality, hint=self.name, **common)
        inner.set_limit(self.limit_kb)
        self.inner = inner

    def _native_plan(self):
        """YouTube (and anything AeroGrab's own engine already failed on) goes straight to yt-dlp's downloader: no separate lookup first."""
        stem = os.path.splitext(clean_name(self.hint))[0] if self.hint else ""
        return {"title": stem, "referer": self.referer, "ua": self.ua, "url": "", "audio": "", "kind": "native", "name": (stem or "video") + ".mp4"}

    def _run(self):
        try:
            for attempt in (0, 1, 2):
                if self.inner is None:
                    self.note = "extracting stream links..."
                    plan = self._native_plan() if (self._native_first or is_youtube_url(self.url)) else \
                        ytdlp_resolve(self.url, self.quality, self.referer, self.cookie, self.ua)
                    if self.stop.is_set():
                        self.status, self.note, self.speed = "Paused", "", 0
                        return
                    self._build(plan)
                    self.note = ""
                inner = self.inner
                if inner.status != "Completed":
                    inner.start()
                self.status = "Downloading"
                self._last = (time.time(), self.done)
                while not self.stop.is_set():
                    self._sync()
                    if inner.status in ("Completed", "Error"):
                        break
                    time.sleep(0.2)
                if inner.thread:
                    inner.thread.join(timeout=15)
                self._sync()
                if inner.status == "Completed":
                    self.name, self.path = inner.name or self.name, inner.path
                    self.status = "Completed"
                elif inner.status == "Error":
                    err = inner.error or ""
                    local = re.search(r"no space|disk full|permission|access is denied|read-only", err, re.I)  # this computer's problem, not the site's
                    if not isinstance(inner, NativeYt) and not local:
                        if attempt == 0 and re.search(r"\b(401|403|404|410)\b|expired|forbidden", err, re.I):
                            self._drop_inner()  # signed stream links expire: ask yt-dlp for fresh ones (AeroGrab's fast engine again)
                            continue
                        if attempt < 2:  # v1.8.1: throttled / refused / failed again: yt-dlp's own downloader is the dependable last try
                            self._drop_inner()
                            self._native_first = True
                            self.note = "retrying with yt-dlp's downloader..."
                            continue
                    self.error, self.status = err or "download failed", "Error"
                    self.transient = inner.transient
                else:
                    self.status = "Paused"
                break
        except Exception as e:
            code, hint = explain_ytdlp_error(e)
            self.error, self.status = (hint + "  [" + re.sub(r"\s+", " ", str(e))[:140] + "]") if hint else str(e), "Error"
        self.speed = 0


SETTINGS_FILE = os.path.join(CFG_DIR, "settings.json")
DEFAULT_SETTINGS = {"limit_kb": 0, "sched_on": False, "start": "01:00", "stop": "07:00", "after": "none", "quality": 0,
                    "folder": "", "auto_sort": True, "categories": DEFAULT_CATEGORIES, "queues": [MAIN_QUEUE], "connections": 8, "max_active": 0,
                    "tray": True, "close_to_tray": True, "notify": True, "start_minimized": False,
                    "native_register": True, "autostart_from_browser": True, "extension_ids": [],
                    "check_updates": True,
                    "show_complete_dialog": True, "confirm_captured": True,
                    "proxy_mode": "system", "proxy_type": "http", "proxy_host": "", "proxy_port": 0, "proxy_user": "", "proxy_pass": "",
                    "proxy_bypass": "", "site_logins": [], "auto_retry": True, "retry_max": 5,
                    "theme": "dark", "accent": DEFAULT_ACCENT, "skin": "default",
                    "av_scan": True, "av_engine": "auto", "smart_unwrap": True,
                    "clip_watch": False, "widget_on": False, "widget_x": None, "widget_y": None, "widget_alpha": 90,
                    "toolbar_items": None, "toolbar_style": "both", "toolbar_size": "large",
                    "sound": True, "sound_complete": True, "sound_all_done": True, "sound_error": True, "sound_unfocused_only": False,
                    "sound_quiet": False, "sound_quiet_from": "22:00", "sound_quiet_to": "07:00", "sound_files": {},
                    # --- Configuration window (browser capture rules, saving, connection, click / typing sounds) ---
                    "capture_downloads": True, "capture_types": " ".join(sorted({e for c in DEFAULT_CATEGORIES if c["name"] != "Images" for e in c["exts"]})),
                    "skip_types": DEFAULT_SKIP_TYPES, "capture_unknown": True, "exclude_sites": "", "min_size_kb": 0,
                    "key_prevent": "alt", "key_force": "none", "capture_browsers": {k: True for k, _ in BROWSER_NAMES},
                    "ctx_link": True, "ctx_media": True, "video_button": True, "autostart": False, "clip_monitor": False,
                    "temp_folder": "", "dup_links": "ask", "file_exists": "rename", "timeout": 30, "retries": 6,
                    }


class Manager:
    NET_POLL, NET_FRESH = 5, 15  # seconds: how often the network is checked while retries wait, and how old a 'yes' may be

    def __init__(self, max_active=3, persist=True):
        self.items, self.max_active, self.persist = [], max_active, persist
        self.scanner_on = False  # the window switches this on; the CLI and the tests scan only when asked
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self._busy, self._base = False, 0
        if persist:
            self.load_settings()
            self.load()
        self._fix_categories()
        self._fix_queues()
        if int(self.settings.get("max_active") or 0) > 0:
            self.max_active = int(self.settings["max_active"])
        for d in self.items:
            d.router = self.route
            d.queue = d.queue if d.queue in self.settings["queues"] else MAIN_QUEUE
        GLOBAL_LIMIT.set_rate(self.settings["limit_kb"] * 1024)
        self.net_check, self._net_up, self._net_done, self._net_start, self._net_busy = default_net_check, True, 0.0, 0.0, False
        self.apply_network()

    def apply_network(self):
        """(Re)build the connection layer from the proxy / login settings."""
        OPENER.configure(self.settings)

    def will_retry(self, d):
        st = self.settings
        return bool(st.get("auto_retry", True) and d.status == "Error" and d.transient and d.retries < int(st.get("retry_max", 5) or 0))

    def _net_poll(self, now):
        """Is the network reachable? Asked in the background (never blocks the window). True only for a recent 'yes'."""
        if now - self._net_start >= self.NET_POLL and not self._net_busy:
            self._net_busy, self._net_start = True, now

            def run():
                try:
                    ok = bool(self.net_check())
                except Exception:
                    ok = False
                self._net_up, self._net_done, self._net_busy = ok, time.time(), False
            threading.Thread(target=run, daemon=True).start()
        return self._net_up and now - self._net_done < self.NET_FRESH

    def _auto_retry_step(self, now):
        """Failed downloads that failed for a temporary reason (network, busy server) are tried again after a growing pause - but only while the network is up."""
        waiting = [d for d in self.items if self.will_retry(d)]
        for d in self.items:
            if d.retry_at and not any(d is w for w in waiting):
                d.retry_at = 0.0
        if not waiting:
            return
        online = self._net_poll(now)
        for d in waiting:
            if not d.retry_at:
                d.retry_at = now + RETRY_DELAYS[min(d.retries, len(RETRY_DELAYS) - 1)]
            elif now >= d.retry_at and online:
                d.retries += 1
                d.retry_at, d._auto_retry, d.status = 0.0, True, "Queued"

    def find_duplicate(self, url):
        """The download already in the list for this link (any status), or None."""
        key = normalize_url(url.strip())
        return next((d for d in self.items if d.url == key), None)

    def add(self, url, folder, connections=8, kind=None, **extra):
        url = url.strip()
        if kind is None:
            kind = detect_kind(url)  # hls (.m3u8) / dash (.mpd) / ftp / ytdlp (YouTube, Facebook, Instagram ...) / plain file
        checksum = normalize_checksum(extra.pop("checksum", ""))  # raises ValueError for a value that isn't a hash
        queue_name = extra.pop("queue", None) or MAIN_QUEUE
        project, later, desc = extra.pop("project", ""), extra.pop("later", False), extra.pop("desc", "")
        if kind == "mux":
            d = MuxDownload(url, folder, connections, **extra)
        elif kind == "ftp":
            d = FtpDownload(url, folder, connections, **extra)
        elif kind == "dash":
            d = DashDownload(url, folder, connections, quality=extra.pop("quality", None) or self.settings.get("quality", 0), **extra)
        elif kind == "ytdlp":
            q = extra.pop("quality", None)
            d = ExtractDownload(url, folder, connections, quality=self.settings.get("quality", 0) if q is None else q, **extra)
        elif kind == "hls":
            q = extra.pop("quality", None)
            d = HlsDownload(url, folder, connections, quality=self.settings.get("quality", 0) if q is None else q, **extra)
        else:
            d = Download(url, folder, connections, **extra)
        d.router = self.route
        guess = d.hint or urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
        if kind == "ytdlp" and not d.hint:
            guess = "video.mp4"  # the real title comes from the video page
        if kind in ("hls", "mux", "dash", "ytdlp") and not os.path.splitext(guess)[1]:
            guess += ".mp4"
        d.category = classify(self.settings["categories"], guess, url)  # provisional: refined once the real file name is known
        d.queue = queue_name if queue_name in self.settings["queues"] else MAIN_QUEUE
        d.project, d.checksum = project, checksum
        d.desc = desc or urllib.parse.urlparse(d.referer or d.url).netloc
        if later:
            d.status = "Paused"  # "Download later": waits in its queue until you start it
        self.items.append(d)
        return d

    # ----- settings -----
    def load_settings(self):
        try:
            with open(SETTINGS_FILE) as f:
                self.settings.update(json.load(f))
        except (OSError, ValueError):
            pass

    def _fix_categories(self):
        """Keep the list sane even if settings.json was edited by hand: General always exists and comes first."""
        good = []
        for c in self.settings.get("categories") or []:
            if isinstance(c, dict) and isinstance(c.get("name"), str) and c["name"].strip():
                good.append({"name": c["name"].strip(), "folder": str(c.get("folder") or ""),
                             "exts": [str(x).lower().lstrip(".") for x in c.get("exts", [])],
                             "sites": [str(x).lower() for x in c.get("sites", [])]})
        if not any(c["name"] == "General" for c in good):
            good.insert(0, _cat("General"))
        good.sort(key=lambda c: c["name"] != "General")
        self.settings["categories"] = good

    def _fix_queues(self):
        names = []
        for q in [MAIN_QUEUE] + [x for x in (self.settings.get("queues") or []) if isinstance(x, str)]:
            q = q.strip()[:40]
            if q and q.lower() not in [n.lower() for n in names]:
                names.append(q)
        self.settings["queues"] = names

    # ----- queues, projects -----
    def _queue_name(self, name, exclude=None):
        name = (name or "").strip()
        if not name or len(name) > 40 or any(ch in name for ch in '/\\:*?"<>|'):
            raise ValueError("Give the queue a short name without  / \\ : * ? \" < > |")
        if any(q.lower() == name.lower() and q != exclude for q in self.settings["queues"]):
            raise ValueError(f"There is already a queue called {name!r}.")
        return name

    def add_queue(self, name):
        name = self._queue_name(name)
        self.settings["queues"].append(name)
        self.save_settings()
        return name

    def rename_queue(self, old, new):
        if old == MAIN_QUEUE:
            raise ValueError("The main queue can't be renamed.")
        new = self._queue_name(new, exclude=old)
        self.settings["queues"] = [new if q == old else q for q in self.settings["queues"]]
        for d in self.items:
            if d.queue == old:
                d.queue = new
        self.save_settings()
        return new

    def delete_queue(self, name):
        if name == MAIN_QUEUE:
            raise ValueError("The main queue can't be deleted.")
        self.settings["queues"] = [q for q in self.settings["queues"] if q != name]
        for d in self.items:
            if d.queue == name:
                d.queue = MAIN_QUEUE
        self.save_settings()

    def move_to_queue(self, d, name):
        if name not in self.settings["queues"]:
            raise ValueError(f"There is no queue called {name!r}")
        d.queue = name

    def start_queue(self, name):
        """Queue every stopped/failed download of the queue (the scheduler window still applies)."""
        n = 0
        for d in self.items:
            if d.queue == name and d.status in ("Paused", "Error"):
                d.status, d.auto_paused = "Queued", False
                n += 1
        return n

    def stop_queue(self, name):
        n = 0
        for d in self.items:
            if d.queue == name and (d.status in ACTIVE or d.status == "Queued"):
                d.auto_paused = d.force = False
                if d.status in ACTIVE:
                    d.pause()
                else:
                    d.status = "Paused"
                n += 1
        return n

    def projects(self):
        return sorted({d.project for d in self.items if d.project}, key=str.lower)

    # ----- export / import -----
    def export_list(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"aerograb": __version__, "downloads": [d.to_dict() for d in self.items]}, f, indent=1)
        return len(self.items)

    def import_list(self, path, folder):
        """Import an AeroGrab export (.json) or any text file containing links. Imported items start stopped."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        added = 0
        try:
            data = json.loads(text)
            rows = data["downloads"] if isinstance(data, dict) else data
            for x in rows:
                if not isinstance(x, dict) or not str(x.get("url", "")).startswith(URL_SCHEMES):
                    continue
                if any(d.url == x["url"] and d.name == x.get("name") for d in self.items):
                    continue
                d = Download.from_dict(x)
                d.router = self.route
                d.queue = d.queue if d.queue in self.settings["queues"] else MAIN_QUEUE
                self.items.append(d)
                added += 1
            return added
        except (ValueError, KeyError, TypeError):
            pass
        for u in dict.fromkeys(re.findall(r"https?://[^\s<>\"']+", text)):
            self.add(u, folder, later=True)
            added += 1
        return added

    def route(self, d):
        """Called when a download learns its real file name: set its category and, if auto-sort is on, its folder."""
        if not d.auto_cat:
            return
        cats = self.settings["categories"]
        d.category = classify(cats, d.name or "", d.url)
        if self.settings.get("auto_sort", True):
            d.folder = category_folder(cats, d.category, d.base)

    def move_to_category(self, d, name):
        """Pin a download to a category: before it starts that changes where it will be saved; once finished the file is moved."""
        cats = self.settings["categories"]
        if not any(c["name"] == name for c in cats):
            raise ValueError(f"There is no category called {name!r}")
        if d.path and d.status != "Completed":
            raise ValueError("Pause and remove it, or wait until it finishes: a partly downloaded file can't be moved.")
        dest = category_folder(cats, name, d.base)
        if d.path and os.path.exists(d.path):
            os.makedirs(dest, exist_ok=True)
            target = unique_path(dest, os.path.basename(d.path))
            shutil.move(d.path, target)
            d.path, d.name = target, os.path.basename(target)
        d.category, d.auto_cat, d.folder = name, False, dest

    def save_settings(self):
        if not self.persist:
            return
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f)
        try:
            os.chmod(SETTINGS_FILE, 0o600)  # it can hold a proxy password and site logins: this user only
        except OSError:
            pass

    def set_limit_kb(self, kb):
        self.settings["limit_kb"] = max(0, int(kb))
        GLOBAL_LIMIT.set_rate(self.settings["limit_kb"] * 1024)
        self.save_settings()

    def in_window(self, now_min=None):
        """True when downloads may run (always, unless the scheduler is on). Handles overnight windows."""
        st = self.settings
        if not st["sched_on"]:
            return True
        if now_min is None:
            t = time.localtime()
            now_min = t.tm_hour * 60 + t.tm_min
        try:
            a, b = parse_hm(st["start"]), parse_hm(st["stop"])
        except ValueError:
            return True
        if a == b:
            return True
        return a <= now_min < b if a < b else (now_min >= a or now_min < b)

    # ----- queue + scheduler; returns True once when a batch of downloads has just finished -----
    def schedule(self):
        allowed = self.in_window()
        now = time.time()
        if self.settings.get("auto_retry", True):
            self._auto_retry_step(now)
        for d in self.items:
            if d.status == "Completed" and d.checksum and not d.verified and not d._verifying:
                d.verify_async()  # hash the finished file in the background
        if self.scanner_on and self.settings.get("av_scan", True):
            for d in self.items:
                if d.status == "Completed" and not d.scan and not d._scanning and not d._scan_skip and d.path:
                    d.scan_async(self.settings.get("av_engine", "auto"))
        for d in self.items:
            if allowed and d.auto_paused and d.status == "Paused":
                d.auto_paused, d.status = False, "Queued"
            elif not allowed and d.status in ACTIVE and not d.force:
                d.auto_paused = True
                d.pause()
        active = sum(d.status in ACTIVE for d in self.items)
        cur = sum(d.speed for d in self.items if d.status in ACTIVE)
        if cur > 0:
            self.speed_seen = cur if not getattr(self, "speed_seen", 0) else 0.9 * self.speed_seen + 0.1 * cur
        for d in self.items:
            if active >= self.max_active:
                break
            if d.status == "Queued" and (allowed or d.force):
                d.start()
                active += 1
        for d in self.items:
            d.update_speed()
        pending = any(d.status in ACTIVE or d.status == "Queued" or (d.auto_paused and d.status == "Paused")
                      for d in self.items)
        done = sum(d.status == "Completed" for d in self.items)
        if pending:
            if not self._busy:
                self._busy, self._base = True, done
        elif self._busy:
            self._busy = False
            return done > self._base
        return False

    def kick(self):
        """Start queued downloads right now instead of at the next 500 ms tick (used when the user clicks Start Download)."""
        allowed = self.in_window()
        active = sum(d.status in ACTIVE for d in self.items)
        for d in self.items:
            if active >= self.max_active:
                break
            if d.status == "Queued" and (allowed or d.force):
                d.start()
                active += 1

    def remove(self, d, delete_file=False, delete_completed=False):
        d.pause()
        if d.thread:
            d.thread.join(timeout=3)
        if delete_file and d.status != "Completed":
            getattr(d, "discard", lambda: None)()  # temp folders of HLS / video+audio downloads
        if delete_completed and d.status == "Completed" and d.path and os.path.exists(d.path):
            try:
                os.remove(d.path)
            except OSError:
                pass
        if delete_file and d.path and d.status != "Completed" and os.path.exists(d.path):
            try:
                os.remove(d.path)
            except OSError:
                pass
        self.items.remove(d)

    def save(self):
        os.makedirs(CFG_DIR, exist_ok=True)
        tmp = DB_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump([d.to_dict() for d in self.items], f)
        os.replace(tmp, DB_FILE)

    def load(self):
        try:
            with open(DB_FILE) as f:
                self.items = [Download.from_dict(x) for x in json.load(f)]
        except (OSError, ValueError, KeyError):
            self.items = []

    def shutdown(self):
        for d in self.items:
            d.pause()
        for d in self.items:
            if d.thread:
                d.thread.join(timeout=3)
        self.save()


STALE_CAPTURE_SECS = 90      # a browser request older than this is ignored
CAPTURE_DEDUPE_SECS = 30     # the same link offered again within this time is ignored
CAPTURE_PUMP_MS = 25         # how often the GUI looks for a link the browser just sent (v1.8: was 100 ms) - an empty look costs microseconds
CAPTURE_EXPIRE_SECS = 300    # a confirmation that waited this long unanswered is dropped
CAPTURE_MAX_QUEUE = 10


# ====================== Browser integration API ======================
def get_token(state_dir=None):
    state_dir = state_dir or CFG_DIR
    os.makedirs(state_dir, exist_ok=True)
    p = os.path.join(state_dir, "token")
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        t = secrets.token_urlsafe(24)
        with open(p, "w") as f:
            f.write(t)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        return t


META_SOURCES = ("yt-dlp", "page", "stream")


def sanitize_meta(m):
    """What the browser knows about a capture (site, title, quality, duration, size ...), cleaned up: wrong types and absurd values are dropped,
    text is trimmed. Purely informational - it only decorates the dialog, it never decides what is downloaded."""
    if not isinstance(m, dict):
        return {}
    out = {}
    for k, n in (("site", 40), ("title", 200)):
        v = m.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = re.sub(r"[\x00-\x1f]+", " ", v).strip()[:n]
    ext = m.get("ext")
    if isinstance(ext, str) and re.fullmatch(r"[A-Za-z0-9]{1,8}", ext):
        out["ext"] = ext.lower()
    for k, hi in (("height", 8640), ("width", 15360), ("duration", 86400 * 3), ("size", 1 << 44)):
        v = m.get(k)
        if type(v) in (int, float) and 0 < v <= hi:
            out[k] = int(v)
    if m.get("source") in META_SOURCES:
        out["source"] = m["source"]
    if m.get("audio") is True:
        out["audio"] = True
    return out


def capture_summary(meta, kind=None):
    """The line the capture dialog shows instead of 'Checking...': '1080p - MP4 - 12:34 - about 85.2 MB  (YouTube)'. '' when the browser told us nothing."""
    m = meta if isinstance(meta, dict) else {}
    parts = []
    if m.get("audio"):
        parts.append("Audio only")
    elif m.get("height"):
        parts.append(f"{m['height']}p")
    if m.get("ext"):
        parts.append(str(m["ext"]).upper())
    d = int(m.get("duration") or 0)
    if d > 0:
        parts.append(f"{d // 3600}:{d % 3600 // 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60}:{d % 60:02d}")
    if m.get("size"):
        parts.append(("about " if m.get("source") in ("page", "yt-dlp") or kind == "ytdlp" else "") + human(m["size"]))
    if not parts:
        return ""
    return " \u00b7 ".join(parts) + (f"   ({m['site']})" if m.get("site") else "")


def start_api(mgr, defaults, port=API_PORT, token=None, state_dir=None, confirm=None):
    """Local-only API for the browser extension. Needs the pairing token AND an
    extension Origin (web pages cannot forge Origin) AND a localhost Host header
    (blocks DNS rebinding).
    confirm(job): when given (the GUI), captured links are handed to it instead of being added -
    nothing downloads until the user clicks Start. job = {url, folder, connections, kind, kw}."""
    token = token or get_token(state_dir)
    fcache, fcache_lock = {}, threading.Lock()  # url -> (time, stream list): extraction takes seconds, so repeat opens of the menu reuse it
    inflight = {}  # url -> {"ev": Event, "res": dict}: a lookup already running for this address; later callers wait for it instead of starting yt-dlp again

    class H(http.server.BaseHTTPRequestHandler):
        # v1.8: HTTP/1.1 keep-alive (the native host reuses one connection), TCP_NODELAY and ONE buffered write per response. With the old
        # unbuffered writer the headers and the body left as two small segments; on Windows the second waits for the first one's delayed ACK.
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True
        wbufsize = 65536
        timeout = 60  # an idle keep-alive connection frees its thread after a minute

        def log_message(self, *a):
            pass

        def _origin_ok(self):
            o, host = self.headers.get("Origin", ""), self.headers.get("Host", "")
            # Chrome omits Origin on some extension requests, so allow none; but a web page's
            # Origin is always sent on cross-origin POST/preflight and is rejected here.
            return (o == "" or o.startswith(("chrome-extension://", "moz-extension://"))) and \
                host in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _send(self, code, obj=None):
            body = json.dumps(obj or {}).encode()
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", ""))
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-AeroGrab-Token")
            self.send_header("Vary", "Origin")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def _auth(self):
            if not self._origin_ok():
                self.close_connection = True  # the request body (if any) was not read: don't treat it as the next request
                self._send(403, {"error": "forbidden origin"})
            elif not secrets.compare_digest(self.headers.get("X-AeroGrab-Token", ""), token):
                self.close_connection = True
                self._send(401, {"error": "bad token"})
            else:
                return True
            return False

        def do_OPTIONS(self):
            self._send(200 if self._origin_ok() else 403)

        def do_GET(self):
            if self.path == "/ping" and self._auth():
                self._send(200, {"app": "AeroGrab", "version": 1})
            elif self.path == "/config" and self._auth():
                self._send(200, browser_config(mgr.settings))  # capture rules for the extension
            elif self.path not in ("/ping", "/config"):
                self._send(404, {"error": "not found"})

        def _body(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
                d = json.loads(self.rfile.read(min(n, 1 << 20)))
                url = str(d["url"])
                if not url.startswith(("http://", "https://")):
                    raise ValueError("unsupported scheme")
                return d, url
            except (ValueError, KeyError, TypeError):
                self.close_connection = True
                self._send(400, {"error": "bad request"})
                return None, None

        def _formats_payload(self, d, url):
            """The (slow) lookup itself: a dict {ok, ...}. Never raises.
            v1.8.1: a failure carries a `code` and a plain-words `hint` (the menu shows them), and a failure that looks like 'yt-dlp is out of date'
            triggers one forced update + one retry before giving up."""
            args = (url, d.get("referer") or None, d.get("cookie") or None, d.get("userAgent") or None)
            info, err = None, None
            for attempt in (0, 1):
                try:
                    info = ytdlp_formats(*args)
                    break
                except IOError as e:
                    if str(e) == YT_MISSING:
                        return {"ok": False, "error": str(e), "missing": True, "code": "missing", "hint": YT_MISSING}
                    err = e
                except Exception as e:
                    err = e
                code, _ = explain_ytdlp_error(err)
                if attempt == 0 and code in ("outdated", "format", "js_runtime") and _yt_setting("auto_ytdlp_update", True) \
                        and not os.environ.get("AEROGRAB_NO_YTDLP_UPDATE"):
                    ensure_js_runtime_async()
                    if ytdlp_update(force=True).get("updated"):
                        continue
                break
            if info is None:
                code, hint = explain_ytdlp_error(err)
                if code == "js_runtime" and YT_ENV["installing"]:
                    hint = "AeroGrab is installing the YouTube helper (Deno) right now. Try again in a minute."
                return {"ok": False, "code": code, "hint": hint, "error": "yt-dlp could not read this video: " + re.sub(r"\s+", " ", str(err))[:200]}
            info["ok"] = True
            with fcache_lock:
                if len(fcache) > 50:
                    fcache.clear()
                fcache[url] = (time.time(), info)
            return info

        def _formats(self):
            """The video menu in the browser: which qualities does this page offer (via yt-dlp), their sizes, and how fast is this machine's connection.
            v1.8: one yt-dlp run per address at a time. The look-ahead (started when the video begins playing) and the menu the user opens a moment later
            used to start TWO identical extractions; now the second caller waits for the first one's answer."""
            d, url = self._body()
            if d is None:
                return
            speed = getattr(mgr, "speed_seen", 0.0)
            if not media_site(url):
                return self._send(200, {"ok": False, "error": "not a video page", "speed": speed})
            with fcache_lock:
                hit = fcache.get(url)
                if hit and time.time() - hit[0] < 300:
                    cached, mine, box = hit[1], False, None
                else:
                    cached, box = None, inflight.get(url)
                    mine = box is None
                    if mine:
                        inflight[url] = box = {"ev": threading.Event(), "res": None}
            if cached is not None:
                return self._send(200, dict(cached, speed=speed))
            if not mine:
                box["ev"].wait(120)
                res = box["res"] or {"ok": False, "error": "yt-dlp took too long"}
                return self._send(200, dict(res, speed=speed))
            res = {"ok": False, "error": "yt-dlp failed"}
            try:
                res = self._formats_payload(d, url)
            finally:
                box["res"] = res
                with fcache_lock:
                    inflight.pop(url, None)
                box["ev"].set()
            self._send(200, dict(res, speed=speed))

        def do_POST(self):
            if self.path == "/formats":
                if self._auth():
                    self._formats()
                return
            if self.path == "/config":
                if self._auth():
                    self._send(200, browser_config(mgr.settings))
                return
            if self.path != "/add":
                self.close_connection = True
                return self._send(404, {"error": "not found"})
            if not self._auth():
                return
            d, url = self._body()
            if d is None:
                return
            if d.get("drm") is True:  # the extension already refuses these; a second line of defence, never a bypass
                return self._send(422, {"error": "DRM-protected content is not downloaded"})
            ts = d.get("ts")  # when the browser says the user started it (ms); old requests are never shown
            if isinstance(ts, (int, float)) and not isinstance(ts, bool) and abs(time.time() - ts / 1000.0) > STALE_CAPTURE_SECS:
                return self._send(409, {"error": "stale request ignored"})
            folder, conns = defaults()
            kind_in = d.get("kind")
            hls, yt, dash = kind_in == "hls", kind_in == "ytdlp", kind_in == "dash"
            pick = {}
            for src, dst in (("quality", "quality"), ("bandwidth", "pick_bw")):
                if hls and type(d.get(src)) is int and d[src] > 0:
                    pick[dst] = d[src]
            if yt and type(d.get("quality")) is int and (0 < d["quality"] <= 8640 or d["quality"] == -1):
                pick["quality"] = d["quality"]  # height cap, or -1 = audio only
            audio = d.get("audioUrl")
            mux = not (hls or yt or dash) and isinstance(audio, str) and audio.startswith(("http://", "https://"))
            if mux:
                pick["audio_url"] = audio
            kw = dict(pick, referer=d.get("referer") or None, cookie=d.get("cookie") or None,
                      ua=d.get("userAgent") or None, hint=clean_name(d["filename"]) if d.get("filename") else None)
            job = {"url": url, "folder": folder, "connections": conns, "kind": "hls" if hls else "ytdlp" if yt else "dash" if dash else "mux" if mux else None, "kw": kw,
                   "meta": sanitize_meta(d.get("meta")), "_rx": time.perf_counter()}
            if confirm is not None:
                confirm(job)
            else:
                mgr.add(job["url"], job["folder"], job["connections"], kind=job["kind"], **kw)
            self._send(200, {"ok": True})

    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    except OSError:
        return None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    write_api_hint(port, state_dir)
    return srv


def write_api_hint(port, state_dir=None):
    """Tell the native-messaging host which port this instance listens on (it falls back to 6800)."""
    try:
        d = state_dir or CFG_DIR
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "api.json"), "w") as f:
            json.dump({"port": port, "pid": os.getpid()}, f)
    except OSError:
        pass


# ============================ browser integration: native messaging ============================
# The browser extension talks to AeroGrab through a "native messaging host": a program the *browser* starts on demand,
# but only for extension IDs listed in the host's manifest. Browsers find the manifest through the Windows Registry
# (HKCU\Software\<vendor>\NativeMessagingHosts\<name>) or, on Linux/macOS, a per-browser folder. The host is simply
# AeroGrab started in a special mode (`--native-host`); it forwards each message to AeroGrab's local server and, if
# AeroGrab isn't running, starts it first. The extension therefore needs no port and no pairing token.
NATIVE_HOST_NAME = "org.aerograb.nativehost"
DEFAULT_EXTENSION_IDS = ("jngcdhpgdacflokoombdcimnonfngiff",)  # fixed by the "key" in extension/manifest.json (tools/extension_id.py)
FIREFOX_EXTENSION_ID = "aerograb@alter-xsource404.github.io"                    # the gecko id in extension/manifest.firefox.json
HOST_JOB_KEYS = ("url", "referer", "filename", "kind", "quality", "bandwidth", "audioUrl", "cookie", "userAgent", "ts", "meta", "drm")
MAX_NATIVE_MESSAGE = 1 << 20

# key, label, Windows registry path under HKCU, Linux folder, macOS folder, manifest flavour
BROWSERS = (
    ("chrome", "Google Chrome", r"Software\Google\Chrome\NativeMessagingHosts", "~/.config/google-chrome/NativeMessagingHosts",
     "~/Library/Application Support/Google/Chrome/NativeMessagingHosts", "chromium"),
    ("edge", "Microsoft Edge", r"Software\Microsoft\Edge\NativeMessagingHosts", "~/.config/microsoft-edge/NativeMessagingHosts",
     "~/Library/Application Support/Microsoft Edge/NativeMessagingHosts", "chromium"),
    ("brave", "Brave", r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts", "~/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts",
     "~/Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts", "chromium"),
    ("chromium", "Chromium", r"Software\Chromium\NativeMessagingHosts", "~/.config/chromium/NativeMessagingHosts",
     "~/Library/Application Support/Chromium/NativeMessagingHosts", "chromium"),
    ("firefox", "Mozilla Firefox", r"Software\Mozilla\NativeMessagingHosts", "~/.mozilla/native-messaging-hosts",
     "~/Library/Application Support/Mozilla/NativeMessagingHosts", "firefox"),
)
ALWAYS_REGISTER = ("chrome", "edge")  # on Windows these are registered even before any trace of the browser exists


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def extension_ids(extra=()):
    """The built-in extension ID plus any the user added (e.g. a Chrome Web Store ID), validated."""
    ids = list(DEFAULT_EXTENSION_IDS) + [str(i).strip().lower() for i in extra]
    return tuple(dict.fromkeys(i for i in ids if re.fullmatch(r"[a-p]{32}", i)))


class NativeIntegration:
    """Registers (and removes) AeroGrab's native-messaging host for the installed browsers.
    Windows: manifest files under <state>/native plus a value in HKCU\\Software\\<vendor>\\NativeMessagingHosts\\<name>.
    Linux/macOS: the manifest is written into each browser's NativeMessagingHosts folder."""

    def __init__(self, extra_ids=(), state_dir=None, home=None, system=None, winreg_module=None, frozen=None, executable=None, script=None):
        self.ids = extension_ids(extra_ids)
        self.state_dir = state_dir or CFG_DIR
        self.native_dir = os.path.join(self.state_dir, "native")
        self.home = home or os.path.expanduser("~")
        self.system = system or platform.system()
        self._winreg = winreg_module
        self.frozen = getattr(sys, "frozen", False) if frozen is None else frozen
        self.executable = executable or sys.executable
        self.script = script or os.path.abspath(__file__)

    # ---- what the browser should start
    def _launcher(self):
        """(path, body) of the wrapper the browser should start; body is None when aerograb.exe itself is the host. Writes nothing."""
        if self.frozen:
            return self.executable, None
        if self.system == "Windows":
            exe = self.executable
            if os.path.basename(exe).lower() == "pythonw.exe" and os.path.exists(os.path.join(os.path.dirname(exe), "python.exe")):
                exe = os.path.join(os.path.dirname(exe), "python.exe")  # the host needs a real console process for stdin/stdout
            return os.path.join(self.native_dir, "aerograb-host.bat"), f'@echo off\r\n"{exe}" "{self.script}" %*\r\n'
        return os.path.join(self.native_dir, "aerograb-host.sh"), f'#!/bin/sh\nexec {shlex.quote(self.executable)} {shlex.quote(self.script)} "$@"\n'

    def host_command(self):
        """A program the browser can start with no arguments of ours: aerograb.exe itself when frozen, else a tiny wrapper (created here)."""
        path, body = self._launcher()
        if body is not None:
            os.makedirs(self.native_dir, exist_ok=True)
            if read_text(path) != body:
                with open(path, "w", newline="") as f:
                    f.write(body)
            if self.system != "Windows":
                os.chmod(path, 0o755)
        return path

    def manifest(self, kind, command):
        m = {"name": NATIVE_HOST_NAME, "description": "AeroGrab - hands browser downloads and videos to the AeroGrab download manager",
             "path": command, "type": "stdio"}
        if kind == "firefox":
            m["allowed_extensions"] = [FIREFOX_EXTENSION_ID]
        else:
            m["allowed_origins"] = [f"chrome-extension://{i}/" for i in self.ids]
        return m

    # ---- Windows registry (injectable for tests)
    @property
    def winreg(self):
        if self._winreg is None:
            import winreg
            self._winreg = winreg
        return self._winreg

    def reg_key(self, row):
        return row[2] + "\\" + NATIVE_HOST_NAME

    def _reg_get(self, subkey):
        w = self.winreg
        try:
            with w.OpenKey(w.HKEY_CURRENT_USER, subkey, 0, w.KEY_READ) as k:
                return w.QueryValueEx(k, "")[0]
        except OSError:
            return None

    def _reg_set(self, subkey, value):
        w = self.winreg
        with w.CreateKey(w.HKEY_CURRENT_USER, subkey) as k:
            w.SetValueEx(k, "", 0, w.REG_SZ, value)

    def _reg_delete(self, subkey):
        try:
            self.winreg.DeleteKey(self.winreg.HKEY_CURRENT_USER, subkey)
        except OSError:
            pass

    def _reg_exists(self, subkey):
        w = self.winreg
        try:
            with w.OpenKey(w.HKEY_CURRENT_USER, subkey, 0, w.KEY_READ):
                return True
        except OSError:
            return False

    # ---- per-browser helpers
    def manifest_path(self, row):
        if self.system == "Windows":
            return os.path.join(self.native_dir, row[5], NATIVE_HOST_NAME + ".json")
        d = row[4] if self.system == "Darwin" else row[3]
        return os.path.join(self.home, d[2:], NATIVE_HOST_NAME + ".json")

    def detected(self, row):
        if self.system == "Windows":
            return self._reg_exists(row[2].rsplit("\\", 1)[0])  # the vendor key, e.g. Software\Google\Chrome
        return os.path.isdir(os.path.dirname(os.path.dirname(self.manifest_path(row))))

    def _write_manifest(self, path, data):
        text = json.dumps(data, indent=2) + "\n"
        if read_text(path) != text:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:  # newline="": Windows must not turn \n into \r\n, or status() sees it as outdated
                f.write(text)

    def register(self, only=None):
        """Create/refresh the registration for every installed browser. Safe to run on every start (it only writes what changed)."""
        out, command = [], self.host_command()
        for row in BROWSERS:
            key, label, kind = row[0], row[1], row[5]
            if only and key not in only:
                continue
            found = self.detected(row)
            e = {"key": key, "label": label, "detected": found, "registered": False, "detail": ""}
            if not found and not (self.system == "Windows" and key in ALWAYS_REGISTER):
                e["detail"] = "browser not found"
            else:
                try:
                    mp = self.manifest_path(row)
                    self._write_manifest(mp, self.manifest(kind, command))
                    if self.system == "Windows":
                        self._reg_set(self.reg_key(row), mp)
                    e["registered"], e["detail"] = True, (f"HKCU\\{self.reg_key(row)}" if self.system == "Windows" else mp)
                except OSError as ex:
                    e["detail"] = f"failed: {ex}"
            out.append(e)
        return out

    def status(self):
        """Per browser: registered / outdated / not registered / browser not found. Read-only."""
        out = []
        command, body = self._launcher()
        wrapper_ok = body is None or read_text(command) == body
        for row in BROWSERS:
            key, label, kind = row[0], row[1], row[5]
            mp, found = self.manifest_path(row), self.detected(row)
            have = read_text(mp)
            linked = have is not None and (self.system != "Windows" or self._reg_get(self.reg_key(row)) == mp)
            current = linked and have == json.dumps(self.manifest(kind, command), indent=2) + "\n" and wrapper_ok
            state = "registered" if current else "outdated" if linked else "not registered"
            if state == "not registered" and not found and not (self.system == "Windows" and key in ALWAYS_REGISTER):
                state = "browser not found"
            out.append({"key": key, "label": label, "detected": found, "state": state, "registered": state == "registered"})
        return out

    def unregister(self):
        for row in BROWSERS:
            if self.system == "Windows":
                self._reg_delete(self.reg_key(row))
            try:
                os.remove(self.manifest_path(row))
            except OSError:
                pass


def _basename(p):
    return re.split(r"[\\/]", p)[-1]


def read_text(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except OSError:
        return None


def is_native_host_launch(argv):
    """True when a browser (not a person) started us: Chrome passes the extension origin, Firefox the manifest path + add-on id."""
    a = argv[1:]
    return ("--native-host" in a or any(x.startswith(("chrome-extension://", "moz-extension://")) for x in a)
            or (len(a) >= 2 and _basename(a[0]) == NATIVE_HOST_NAME + ".json"))


def nm_read(stream):
    """One native-messaging message (4-byte length in native byte order + UTF-8 JSON), or None at end of input."""
    raw = stream.read(4)
    if len(raw) < 4:
        return None
    (n,) = struct.unpack("=I", raw)
    if n > MAX_NATIVE_MESSAGE:
        raise ValueError("message too large")
    data = stream.read(n)
    if len(data) < n:
        raise ValueError("truncated message")
    return json.loads(data.decode("utf-8"))


def nm_write(stream, obj):
    data = json.dumps(obj).encode("utf-8")
    stream.write(struct.pack("=I", len(data)) + data)
    stream.flush()


def _std_binary_streams():
    """stdin/stdout as raw binary streams, also for a windowed (no-console) Windows exe where sys.stdin is None."""
    if os.name == "nt":
        import msvcrt
        for fd in (0, 1):
            try:
                msvcrt.setmode(fd, os.O_BINARY)
            except (OSError, ValueError):
                pass
        if getattr(sys, "stdin", None) is None or getattr(sys, "stdout", None) is None:
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.GetStdHandle.restype = ctypes.c_void_p
            hin, hout = k32.GetStdHandle(-10), k32.GetStdHandle(-11)
            return (os.fdopen(msvcrt.open_osfhandle(hin, os.O_RDONLY | os.O_BINARY), "rb", 0),
                    os.fdopen(msvcrt.open_osfhandle(hout, os.O_WRONLY | os.O_BINARY), "wb", 0))
    if getattr(sys, "stdin", None) is not None and getattr(sys, "stdout", None) is not None:
        return sys.stdin.buffer, sys.stdout.buffer
    return os.fdopen(0, "rb", 0), os.fdopen(1, "wb", 0)


def launch_command(frozen=None, executable=None, script=None):
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    exe = executable or sys.executable
    if frozen:
        return [exe, "--minimized"]
    if os.name == "nt" and os.path.basename(exe).lower() == "python.exe" and os.path.exists(os.path.join(os.path.dirname(exe), "pythonw.exe")):
        exe = os.path.join(os.path.dirname(exe), "pythonw.exe")  # no console window for the GUI
    return [exe, script or os.path.abspath(__file__), "--minimized"]


def launch_aerograb():
    """Start the AeroGrab window (minimized, so it sits in the tray) detached from the browser's process tree."""
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen(launch_command(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, **kw)


class HostError(Exception):
    """A problem to report back to the extension (shown in its panel)."""


class NativeHost:
    """The program the browser starts. It trusts only the registered extension IDs, never prints anything but protocol
    bytes, and forwards `add` jobs to the AeroGrab server using the pairing token it reads from disk."""
    LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never route 127.0.0.1 through a system proxy

    def __init__(self, state_dir=None, launch=None, sleep=time.sleep, wait_seconds=20):
        self.state_dir = state_dir or CFG_DIR
        self.launch, self.sleep, self.wait_seconds = launch or launch_aerograb, sleep, wait_seconds

    def log(self, text):
        try:
            p = os.path.join(self.state_dir, "native-host.log")
            os.makedirs(self.state_dir, exist_ok=True)
            if os.path.exists(p) and os.path.getsize(p) > 100_000:
                os.remove(p)
            with open(p, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text.rstrip() + "\n")
        except OSError:
            pass

    def settings(self):
        d = read_json(os.path.join(self.state_dir, "settings.json"), {})
        return d if isinstance(d, dict) else {}

    def _cached(self, name, load):
        """Contents of a small state file, re-read only when the file changed (it used to be read from disk on every single message)."""
        path = os.path.join(self.state_dir, name)
        try:
            st = os.stat(path)
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        box = self.__dict__.setdefault("_cache", {})
        hit = box.get(name)
        if hit and hit[0] == key and key is not None:
            return hit[1]
        val = load()
        box[name] = (key, val)
        return val

    def port(self):
        def load():
            p = read_json(os.path.join(self.state_dir, "api.json"), {}).get("port")
            return p if isinstance(p, int) and 0 < p < 65536 else API_PORT
        return self._cached("api.json", load)

    def token(self):
        return self._cached("token", lambda: get_token(self.state_dir))

    def _conn(self, port, timeout):
        """One keep-alive connection to AeroGrab's local server per thread (the slow 'formats' lookup runs on its own thread, so it never blocks an 'add')."""
        tl = self.__dict__.setdefault("_tl", threading.local())
        c = getattr(tl, "conn", None)
        if c is None or c.port != port:
            if c is not None:
                c.close()
            c = tl.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        return c

    def _drop_conn(self):
        tl = self.__dict__.setdefault("_tl", threading.local())
        c = getattr(tl, "conn", None)
        tl.conn = None
        if c is not None:
            try:
                c.close()
            except OSError:
                pass

    def _request(self, method, path, body=None, timeout=10, limit=4 << 20):
        """(HTTP status, body bytes) of a call to AeroGrab's local server; (0, b"") if nothing is listening. Reuses the connection; one retry if the old one went stale."""
        data = json.dumps(body).encode() if body is not None else None
        port = self.port()
        headers = {"X-AeroGrab-Token": self.token(), "Content-Type": "application/json"}
        for attempt in (0, 1):
            c = self._conn(port, timeout)
            reused = c.sock is not None
            try:
                if reused:
                    c.sock.settimeout(timeout)
                else:
                    c.timeout = timeout
                c.request(method, path, body=data, headers=headers)
                r = c.getresponse()
                raw = r.read(limit)
                if r.will_close:
                    self._drop_conn()
                return r.status, raw
            except (http.client.HTTPException, OSError):
                self._drop_conn()
                if not reused:  # a fresh connection failed: nothing is listening (or it timed out) - retrying would only repeat that
                    return 0, b""
        return 0, b""

    def _call(self, method, path, body=None):
        """HTTP status of a call to AeroGrab's local server (0 if nothing is listening)."""
        return self._request(method, path, body, timeout=10)[0]

    def _json_call(self, path, body, timeout=80):
        """(HTTP status, parsed JSON) of a POST to AeroGrab's local server; (0, None) if nothing is listening."""
        code, raw = self._request("POST", path, body, timeout=timeout)
        if code == 0:
            return 0, None
        try:
            return code, (json.loads(raw or b"{}") if code == 200 else None)
        except ValueError:
            return 0, None

    def alive(self):
        return self._call("GET", "/ping") != 0

    def ensure_running(self):
        if self.alive():
            return
        if not self.settings().get("autostart_from_browser", True):
            raise HostError("AeroGrab isn't running. Start it, or tick 'Start AeroGrab when the browser sends a download' in Browser setup.")
        self.log("AeroGrab not running: starting it")
        self.launch()
        end = time.time() + self.wait_seconds
        while time.time() < end:
            self.sleep(0.05)   # v1.8.2: was 0.25 s - the first window appears as soon as the server answers
            if self.alive():
                return
        raise HostError("AeroGrab was started but did not become ready in time. Open it manually and try again.")

    def handle(self, msg):
        cmd = msg.get("cmd") if isinstance(msg, dict) else None
        if cmd == "ping":
            return {"ok": True, "app": "AeroGrab", "version": __version__, "running": self.alive(), "port": self.port(),
                    "autostart": bool(self.settings().get("autostart_from_browser", True))}
        if cmd == "config":  # capture rules from Configuration; never starts AeroGrab just to ask
            if not self.alive():
                return {"ok": True, "running": False}
            code, obj = self._json_call("/config", {}, timeout=10)
            if code == 200 and isinstance(obj, dict):
                return {"ok": True, "running": True, "config": obj}
            raise HostError("AeroGrab did not answer the settings request.")
        if cmd == "start":
            self.ensure_running()
            return {"ok": True}
        if cmd == "formats":  # the browser's "Download this video" menu asks which qualities a page offers
            job = msg.get("job")
            if not isinstance(job, dict) or not str(job.get("url", "")).lower().startswith(("http://", "https://")):
                raise HostError("That isn't a web address AeroGrab can read.")
            body = {k: job[k] for k in ("url", "referer", "cookie", "userAgent") if job.get(k) not in (None, "")}
            code, obj = self._json_call("/formats", body)  # try first: no extra ping when AeroGrab is already running
            if code == 0:
                if job.get("prefetch"):  # a background look-ahead never starts AeroGrab
                    return {"ok": False, "error": "AeroGrab isn't running", "prefetch": True}
                self.ensure_running()
                code, obj = self._json_call("/formats", body)
            if code == 200 and isinstance(obj, dict):
                return obj
            raise HostError({401: "AeroGrab refused the request (pairing token mismatch). Restart AeroGrab and try again.", 0: "Could not reach AeroGrab."}.get(code, f"AeroGrab answered with error {code}."))
        if cmd == "add":
            job = msg.get("job")
            if not isinstance(job, dict) or not str(job.get("url", "")).lower().startswith(("http://", "https://")):
                raise HostError("That isn't a web address AeroGrab can download.")
            payload = {k: job[k] for k in HOST_JOB_KEYS if job.get(k) not in (None, "")}
            code = self._call("POST", "/add", payload)  # try first: the usual case (AeroGrab is running) costs one request, not two
            if code == 0:
                self.ensure_running()  # only now start AeroGrab
                code = self._call("POST", "/add", payload)
            if code == 200:
                return {"ok": True}
            raise HostError({401: "AeroGrab refused the request (pairing token mismatch). Restart AeroGrab and try again.",
                             400: "AeroGrab did not accept that address.", 0: "Could not reach AeroGrab."}.get(code, f"AeroGrab answered with error {code}."))
        raise HostError("Unknown command.")

    def origin_allowed(self, args):
        extra = self.settings().get("extension_ids", [])
        for a in args:
            if a.startswith("chrome-extension://"):
                return a in [f"chrome-extension://{i}/" for i in extension_ids(extra if isinstance(extra, list) else [])]
            if a.startswith("moz-extension://"):
                return False
        if len(args) >= 2 and _basename(args[0]) == NATIVE_HOST_NAME + ".json":  # Firefox: <manifest path> <add-on id>
            return args[1] == FIREFOX_EXTENSION_ID
        return True  # started by hand with --native-host (testing)

    def serve(self, args, stdin=None, stdout=None):
        args = [a for a in args if a != "--native-host"]
        if not self.origin_allowed(args):
            self.log(f"refused caller: {args}")
            return 2
        if stdin is None or stdout is None:
            stdin, stdout = _std_binary_streams()
        # The extension keeps ONE connection (and so one host process) open. Messages carry an "id" that the reply echoes, and
        # the slow "formats" lookup (yt-dlp, seconds) runs on its own thread so a download hand-over is never queued behind it.
        wlock, workers, closed = threading.Lock(), [], threading.Event()

        def respond(m):
            try:
                reply = self.handle(m)
            except HostError as e:
                reply = {"ok": False, "error": str(e)}
            except Exception as e:
                self.log(f"unexpected: {e!r}")
                reply = {"ok": False, "error": f"Host error: {e}"}
            if isinstance(m, dict) and "id" in m and isinstance(reply, dict):
                reply = dict(reply, id=m["id"])
            with wlock:
                try:
                    nm_write(stdout, reply)
                except OSError:  # the browser closed the pipe
                    closed.set()

        def finish(code):
            for t in workers:
                t.join(timeout=100)
            return code

        while not closed.is_set():
            try:
                msg = nm_read(stdin)
            except (ValueError, struct.error, OSError) as e:
                self.log(f"bad message: {e}")
                with wlock:
                    try:
                        nm_write(stdout, {"ok": False, "error": f"Bad message: {e}"})
                    except OSError:
                        pass
                return finish(1)
            if msg is None:
                break
            if isinstance(msg, dict) and (msg.get("cmd") == "formats" or (msg.get("id") is not None and msg.get("cmd") in ("config", "ping", "start"))):  # v1.8.2: with an id (the extension always sends one) a settings refresh or ping can no longer hold up a download; "add" and id-less messages stay in order on this thread
                t = threading.Thread(target=respond, args=(msg,), daemon=True)
                t.start()
                workers.append(t)
                workers[:] = [w for w in workers if w.is_alive()]
            else:
                respond(msg)
        return finish(0)


# ============================== system tray ==============================
class Tray:
    """System tray icon through the optional `pystray` + `Pillow` packages (Windows and Linux; not macOS, where
    pystray insists on the main thread that the GUI already uses). Menu clicks arrive on pystray's own thread, so
    they are only queued as short command strings; the GUI loop picks them up with poll() and runs them."""
    LIMITS = (0, 256, 512, 1024, 5120)  # KB/s choices in the "Speed limit" submenu (0 = no limit)

    def __init__(self, png_bytes, get_limit=lambda: 0):
        self.cmds, self.icon, self.error = queue.Queue(), None, ""
        if platform.system() == "Darwin":
            self.error = "The tray icon isn't available on macOS."
            return
        try:
            import pystray
            from PIL import Image
            image = Image.open(io.BytesIO(png_bytes))
            image.load()
        except ImportError:
            self.error = "Install the tray add-on first:  pip install pystray pillow"
            return
        except Exception as e:  # e.g. no display / no tray support on this desktop
            self.error = f"The system tray isn't available here ({e})"
            return

        def cmd(name):
            return lambda *a: self.cmds.put(name)

        def label(kb):
            return "No limit" if not kb else f"{kb // 1024} MB/s" if kb % 1024 == 0 else f"{kb} KB/s"
        limits = pystray.Menu(*[pystray.MenuItem(label(kb), cmd(f"limit:{kb}"), radio=True,
                                                 checked=(lambda item, kb=kb: get_limit() == kb)) for kb in self.LIMITS])
        menu = pystray.Menu(
            pystray.MenuItem("Show AeroGrab", cmd("show"), default=True),
            pystray.MenuItem("Pause all", cmd("pause_all")),
            pystray.MenuItem("Resume all", cmd("resume_all")),
            pystray.MenuItem("Speed limit", limits),
            pystray.MenuItem("Open download folder", cmd("folder")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit AeroGrab", cmd("quit")))
        self.icon = pystray.Icon("AeroGrab", image, "AeroGrab", menu)

    @property
    def available(self):
        return self.icon is not None

    def start(self):
        try:
            self.icon.run_detached()
        except Exception as e:
            self.error, self.icon = f"The system tray isn't available here ({e})", None

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass

    def set_title(self, text):
        if self.icon is not None:
            try:
                self.icon.title = text[:127]  # Windows truncates tooltips at 127 characters
            except Exception:
                pass

    def notify(self, message, title="AeroGrab"):
        if self.icon is not None:
            try:
                self.icon.notify(message[:250], title)
            except Exception:
                pass

    def poll(self):
        """Commands clicked in the tray menu since the last call."""
        out = []
        while True:
            try:
                out.append(self.cmds.get_nowait())
            except queue.Empty:
                return out


# ============================== single instance ==============================
class SingleInstance:
    r"""Exactly one AeroGrab GUI per user session (v1.8.4).
    Ownership  : a named Windows mutex (Local\AeroGrab.SingleInstance); elsewhere an flock() on ~/.aerograb/instance.lock.
                 Both are released by the OS when the process dies, so a crash can never leave a stale lock behind.
    IPC        : a named pipe (Windows) / unix socket, guarded by a key derived from the pairing token (multiprocessing.connection).
                 A second launch sends {"cmd": "show"} (or "ping" for --minimized launches: browser / autostart) and exits."""
    MUTEX = "Local\\AeroGrab.SingleInstance"

    def __init__(self, home=None):
        self.home = os.path.abspath(home or CFG_DIR)
        tag = hashlib.sha1(os.path.normcase(self.home).encode("utf-8", "replace")).hexdigest()[:12]
        self.mutex_name = self.MUTEX + ("" if not os.environ.get("AEROGRAB_HOME") and home is None else "." + tag)
        if os.name == "nt":
            self.family, self.address = "AF_PIPE", r"\\.\pipe\AeroGrab." + tag
        else:
            self.family, self.address = "AF_UNIX", os.path.join(self.home, "instance.sock")
            if len(self.address) > 100:
                self.address = os.path.join(tempfile.gettempdir(), f"aerograb-{tag}.sock")
        self._key, self._h, self._fd, self._lis, self._closed = None, None, None, None, False
        self.msgs = queue.Queue()

    @property
    def key(self):
        if self._key is None:
            self._key = hashlib.sha256(("aerograb-instance:" + get_token(self.home)).encode()).digest()
        return self._key

    def acquire(self):
        """True: this process is the one instance. False: another one is running. Unknown errors fail open (better two windows than none)."""
        if os.name == "nt":
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateMutexW.restype, k32.CreateMutexW.argtypes = ctypes.c_void_p, [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
            k32.CloseHandle.argtypes = [ctypes.c_void_p]
            ctypes.set_last_error(0)
            h = k32.CreateMutexW(None, False, self.mutex_name)
            err = ctypes.get_last_error()
            if not h:
                return err != 5  # ACCESS_DENIED: the mutex exists and isn't ours to open
            if err == 183:  # ALREADY_EXISTS
                k32.CloseHandle(h)
                return False
            self._h, self._k32 = h, k32
            return True
        try:
            import fcntl
            os.makedirs(self.home, exist_ok=True)
            fd = os.open(os.path.join(self.home, "instance.lock"), os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                return False
            self._fd = fd
        except (ImportError, OSError):
            pass
        return True

    def serve(self):
        """Start listening for later launches (call right after acquire(), before the window is built). Requests wait in self.msgs."""
        try:
            from multiprocessing.connection import Listener
            if os.name != "nt":
                try:
                    os.unlink(self.address)  # a leftover from a crash (we hold the lock, so nobody else owns it)
                except OSError:
                    pass
                self._lis = Listener(self.address, self.family, backlog=32, authkey=self.key)
            else:
                self._lis = Listener(self.address, self.family, authkey=self.key)
        except Exception:
            self._lis = None
            return False
        threading.Thread(target=self._loop, daemon=True, name="aerograb-ipc").start()
        return True

    def _loop(self):
        while not self._closed:
            try:
                conn = self._lis.accept()
            except Exception:  # listener closed, or a client that failed the key / hung up mid-handshake
                if self._closed:
                    return
                time.sleep(0.05)
                continue
            try:
                if conn.poll(3):
                    m = conn.recv()
                    if isinstance(m, dict):
                        self.msgs.put(m)
                    conn.send("ok")
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.msgs.get_nowait())
            except queue.Empty:
                return out

    def forward(self, msg, timeout=3.0):
        """One attempt to hand `msg` to the running instance. True once it acknowledged. Never blocks longer than `timeout`."""
        res = []

        def work():
            try:
                from multiprocessing.connection import Client
                c = Client(self.address, self.family, authkey=self.key)
                try:
                    c.send(msg)
                    res.append(c.poll(timeout) and c.recv() == "ok")
                finally:
                    c.close()
            except Exception:
                res.append(False)
        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(timeout + 1)
        return bool(res and res[0])

    def close(self):
        """Exit: stop listening and give the lock back (so a restart after Exit / an update starts cleanly)."""
        self._closed = True
        if self._lis is not None:
            try:
                self._lis.close()
            except Exception:
                pass
            self._lis = None
        if os.name != "nt":
            try:
                os.unlink(self.address)
            except OSError:
                pass
        if self._h:
            try:
                self._k32.CloseHandle(self._h)
            except Exception:
                pass
            self._h = None
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


def raise_foreign_window():
    """Last resort (the running instance doesn't answer): find its window by title and bring it up. Windows only."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        u = ctypes.windll.user32
        u.FindWindowW.restype, u.FindWindowW.argtypes = ctypes.c_void_p, [ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        h = u.FindWindowW("TkTopLevel", APP_TITLE)
        if not h:
            return False
        u.ShowWindow(h, 9)  # SW_RESTORE
        u.SetForegroundWindow(h)
        return True
    except Exception:
        return False


def claim_or_forward(minimized=False, wait=20.0, si=None):
    """The start-up gate. Returns the SingleInstance this process now owns (go on and open the GUI), or None when a running
    instance took over the request (this process must exit at once). Rides out the races: the owner still starting up (mutex held,
    pipe not yet listening), the owner just quitting (lock released a moment later) and rapid repeated launches."""
    si = si or SingleInstance()
    if os.name == "nt" and not minimized:
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(0xFFFFFFFF)  # let the running window take focus: this launch was a user action
        except Exception:
            pass
    end = time.time() + wait
    while True:
        if si.acquire():
            si.serve()
            return si
        if si.forward({"cmd": "ping" if minimized else "show"}):
            return None
        if time.time() > end:
            if not minimized:
                raise_foreign_window()
            return None  # something owns the lock but never answers: don't start a second copy
        time.sleep(0.2)


# ============================== GUI (IDM-style window) ==============================
tk = ttk = messagebox = filedialog = simpledialog = None  # tkinter is imported lazily so the CLI works without it

AFTER = {"none": "Do nothing", "exit": "Exit AeroGrab", "shutdown": "Shut down computer"}
MIT_TEXT = """MIT License

Copyright (c) 2026 AeroGrab contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE."""

# (icon, label, App method) - None draws a separator, like IDM's toolbar groups
TOOLBAR = (("add", "Add URL", "add_dialog"), ("resume", "Resume", "resume"), ("stop", "Stop", "stop"), ("stopall", "Stop All", "stop_all"),
           ("delete", "Delete", "delete"), ("delc", "Delete C.", "delete_completed"), None,
           ("options", "Options", "options_dialog"), ("scheduler", "Scheduler", "scheduler_dialog"), None,
           ("startq", "Start Queue", "start_queue"), ("stopq", "Stop Queue", "stop_queue"), None,
           ("grabber", "Grabber", "grabber_dialog"), ("browser", "Browser", "pairing_dialog"))
TOOLBAR_ACTIONS = {e[0]: e for e in TOOLBAR if e}
TOOLBAR_ACTIONS.update(EXTRA_TOOLBAR)
DEFAULT_TOOLBAR = [e[0] if e else "|" for e in TOOLBAR]


def _load_tk():
    global tk, ttk, messagebox, filedialog, simpledialog
    import tkinter as _tk
    from tkinter import ttk as _ttk, messagebox as _mb, filedialog as _fd, simpledialog as _sd
    tk, ttk, filedialog = _tk, _ttk, _fd
    messagebox, simpledialog = messagebox_themed, simpledialog_themed   # themed look-alikes: the OS ones cannot be coloured (see _box)


_UI = {"theme": None}   # the live aerograb_theme.Theme, set by App; the themed dialogs below read fonts / icons / colours from it


def _center_over(win, parent=None):
    """Place a freshly built dialog over its parent window (or the middle of the screen when the parent is hidden in the tray)."""
    try:
        win.update_idletasks()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        if parent is not None and parent.winfo_viewable() and parent.winfo_width() > 50:
            x, y = parent.winfo_rootx() + (parent.winfo_width() - w) // 2, parent.winfo_rooty() + (parent.winfo_height() - h) // 3
        else:
            x, y = (sw - w) // 2, (sh - h) // 3
        win.geometry(f"+{max(0, min(x, sw - w))}+{max(0, min(y, sh - h - 40))}")
    except tk.TclError:
        pass


def _box(title, message, kind="info", buttons=(("OK", True),), default=0, cancel=None, parent=None):
    """The themed replacement for the operating system's message boxes (Windows cannot colour its own, so they stay bright white in
    Dark mode). Modal, keyboard friendly (Enter = default button, Esc = cancel), returns the value of the button that was pressed."""
    th = _UI["theme"]
    parent = parent or getattr(tk, "_default_root", None)
    win = tk.Toplevel(parent)
    win.title(title)
    win.resizable(False, False)
    try:
        win.transient(parent.winfo_toplevel())
    except (tk.TclError, AttributeError):
        pass
    result = [cancel]
    px = th.px if th else (lambda n: n)

    def pick(value):
        result[0] = value
        win.destroy()
    body = ttk.Frame(win, padding=(px(24), px(22), px(24), px(12)))
    body.pack(fill="both", expand=True)
    if th:
        win._icon = th.icon({"info": "info", "warning": "warning", "error": "error", "question": "question"}.get(kind, "info"), 32)
        ttk.Label(body, image=win._icon).pack(side="left", anchor="n", padx=(0, px(16)))
    ttk.Label(body, text=message, wraplength=px(440), justify="left").pack(side="left", anchor="n")
    ttk.Separator(win, orient="horizontal").pack(fill="x", pady=(px(8), 0))
    row = ttk.Frame(win, padding=(px(16), px(12)))
    row.pack(fill="x")
    widgets = []
    for i, (label, value) in reversed(list(enumerate(buttons))):
        b = ttk.Button(row, text=label, style="Accent.TButton" if i == default else "TButton", command=lambda v=value: pick(v))
        b.pack(side="right", padx=(px(8), 0))
        widgets.append((i, b, value))
    win.bind("<Return>", lambda e: pick(buttons[default][1]))
    win.bind("<Escape>", lambda e: pick(cancel))
    win.protocol("WM_DELETE_WINDOW", lambda: pick(cancel))
    _center_over(win, parent)
    try:
        win.grab_set()
    except tk.TclError:
        pass
    for i, b, _ in widgets:
        if i == default:
            b.focus_set()
    win.wait_window()
    return result[0]


class messagebox_themed:
    """Same call signatures as tkinter.messagebox, drawn with the design system."""

    @staticmethod
    def showinfo(title=None, message=None, **kw):
        _box(title or "", message or "", "info", parent=kw.get("parent"))
        return "ok"

    @staticmethod
    def showwarning(title=None, message=None, **kw):
        _box(title or "", message or "", "warning", parent=kw.get("parent"))
        return "ok"

    @staticmethod
    def showerror(title=None, message=None, **kw):
        _box(title or "", message or "", "error", parent=kw.get("parent"))
        return "ok"

    @staticmethod
    def askyesno(title=None, message=None, **kw):
        return bool(_box(title or "", message or "", kw.get("icon", "question"), (("Yes", True), ("No", False)), default=0 if kw.get("default") != "no" else 1, cancel=False, parent=kw.get("parent")))

    @staticmethod
    def askokcancel(title=None, message=None, **kw):
        return bool(_box(title or "", message or "", kw.get("icon", "question"), (("OK", True), ("Cancel", False)), cancel=False, parent=kw.get("parent")))

    @staticmethod
    def askretrycancel(title=None, message=None, **kw):
        return bool(_box(title or "", message or "", kw.get("icon", "warning"), (("Retry", True), ("Cancel", False)), cancel=False, parent=kw.get("parent")))

    @staticmethod
    def askyesnocancel(title=None, message=None, **kw):
        return _box(title or "", message or "", kw.get("icon", "question"), (("Yes", True), ("No", False), ("Cancel", None)), cancel=None, parent=kw.get("parent"))


def _prompt(title, prompt, initial="", parent=None, show=None, check=None):
    """One-line input dialog: returns the entered text, or None when cancelled. `check(text)` may return an error message to keep the dialog open."""
    th = _UI["theme"]
    parent = parent or getattr(tk, "_default_root", None)
    win = tk.Toplevel(parent)
    win.title(title)
    win.resizable(False, False)
    try:
        win.transient(parent.winfo_toplevel())
    except (tk.TclError, AttributeError):
        pass
    px = th.px if th else (lambda n: n)
    out, var, err = [None], tk.StringVar(value="" if initial is None else str(initial)), tk.StringVar()
    body = ttk.Frame(win, padding=(px(22), px(20), px(22), px(6)))
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=prompt, wraplength=px(420), justify="left").pack(anchor="w")
    ent = ttk.Entry(body, textvariable=var, width=46, show=show or "")
    ent.pack(fill="x", pady=(px(10), px(4)))
    ttk.Label(body, textvariable=err, style="Danger.TLabel").pack(anchor="w")
    ttk.Separator(win, orient="horizontal").pack(fill="x", pady=(px(6), 0))
    row = ttk.Frame(win, padding=(px(16), px(12)))
    row.pack(fill="x")

    def ok(_=None):
        msg = check(var.get()) if check else None
        if msg:
            err.set(msg)
            return
        out[0] = var.get()
        win.destroy()
    ttk.Button(row, text="Cancel", command=win.destroy).pack(side="right", padx=(px(8), 0))
    ttk.Button(row, text="OK", style="Accent.TButton", command=ok).pack(side="right")
    win.bind("<Return>", ok)
    win.bind("<Escape>", lambda e: win.destroy())
    _center_over(win, parent)
    try:
        win.grab_set()
    except tk.TclError:
        pass
    ent.focus_set()
    ent.selection_range(0, "end")
    win.wait_window()
    return out[0]


class simpledialog_themed:
    @staticmethod
    def askstring(title, prompt, **kw):
        return _prompt(title, prompt, kw.get("initialvalue", ""), kw.get("parent"), kw.get("show"))

    @staticmethod
    def askinteger(title, prompt, **kw):
        lo, hi = kw.get("minvalue"), kw.get("maxvalue")

        def check(text):
            try:
                v = int(text.strip())
            except ValueError:
                return "Please enter a whole number."
            if lo is not None and v < lo or hi is not None and v > hi:
                return f"Enter a number between {lo if lo is not None else '-'} and {hi if hi is not None else '-'}."
            return None
        r = _prompt(title, prompt, kw.get("initialvalue", ""), kw.get("parent"), None, check)
        return None if r is None else int(r.strip())


class Tip:
    """A small themed tooltip for toolbar buttons and other icon-only controls."""

    def __init__(self, widget, text):
        self.w, self.text, self.tw, self.job = widget, text, None, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _=None):
        self._leave()
        self.job = self.w.after(450, self._show)

    def _show(self):
        self.job = None
        try:
            p = PAL
            tw = self.tw = tk.Toplevel(self.w)
            tw.wm_overrideredirect(True)
            tw.configure(bg=p["border_strong"], bd=0)
            tk.Label(tw, text=self.text() if callable(self.text) else self.text, bg=p["elevated"], fg=p["fg"], font="TkTooltipFont", padx=10, pady=5,
                     justify="left").pack(padx=1, pady=1)
            tw.update_idletasks()
            x = self.w.winfo_rootx() + max(0, (self.w.winfo_width() - tw.winfo_reqwidth()) // 2)
            x = max(0, min(x, self.w.winfo_screenwidth() - tw.winfo_reqwidth()))
            tw.wm_geometry(f"+{x}+{self.w.winfo_rooty() + self.w.winfo_height() + 6}")
        except tk.TclError:
            self.tw = None

    def _leave(self, _=None):
        try:
            if self.job:
                self.w.after_cancel(self.job)
            if self.tw:
                self.tw.destroy()
        except tk.TclError:
            pass
        self.job = self.tw = None


class FloatingWidget:
    """A small always-on-top window with the total speed and a progress ring. Drag it anywhere, double-click to open AeroGrab, right-click for a menu."""
    W, H = 176, 54

    def __init__(self, app):
        self.app, self.win, self.cv, self._drag = app, None, None, None

    @property
    def shown(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except tk.TclError:
            return False

    def show(self):
        if self.shown:
            return
        app, st = self.app, self.app.mgr.settings
        w = self.win = tk.Toplevel(app.root)
        w.configure(bd=0)
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.set_alpha()
        self.cv = tk.Canvas(w, width=self.W, height=self.H, highlightthickness=1, cursor="fleur")
        self.cv.pack()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        x, y = st.get("widget_x"), st.get("widget_y")
        if not isinstance(x, int) or not isinstance(y, int):
            x, y = sw - self.W - 40, sh - self.H - 120  # first time: bottom right
        w.geometry(f"{self.W}x{self.H}+{max(0, min(x, sw - self.W))}+{max(0, min(y, sh - self.H))}")  # never off-screen, even if the monitor setup changed
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._move)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.cv.bind("<Double-Button-1>", lambda e: app.show_window())
        for ev in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            self.cv.bind(ev, self._menu)
        self.update()

    def hide(self):
        try:
            if self.win:
                self.win.destroy()
        except tk.TclError:
            pass
        self.win = self.cv = None

    def set_alpha(self):
        try:
            self.win.attributes("-alpha", max(0.3, min(1.0, int(self.app.mgr.settings.get("widget_alpha", 90)) / 100)))
        except (tk.TclError, ValueError, TypeError, AttributeError):
            pass

    def _press(self, e):
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y(), e.x_root, e.y_root)

    def _move(self, e):
        if self._drag:
            self.win.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _release(self, e):
        if self._drag and (abs(e.x_root - self._drag[2]) > 3 or abs(e.y_root - self._drag[3]) > 3):  # it was dragged, not just clicked: remember where it is
            self.app.mgr.settings["widget_x"], self.app.mgr.settings["widget_y"] = self.win.winfo_x(), self.win.winfo_y()
            self.app.mgr.save_settings()
        self._drag = None

    def _menu(self, e):
        app = self.app
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="Open AeroGrab", command=app.show_window)
        m.add_command(label="Add URL...", command=lambda: (app.show_window(), app.add_dialog()))
        m.add_command(label="Download links from the clipboard", command=app.add_from_clipboard)
        m.add_separator()
        m.add_command(label="Stop all", command=app.stop_all)
        m.add_command(label="Start queue", command=app.start_queue)
        m.add_separator()
        op = tk.Menu(m, tearoff=0)
        for pct in (100, 80, 60, 40):
            op.add_command(label=f"{pct}%", command=lambda p=pct: self.opacity(p))
        m.add_cascade(label="Opacity", menu=op)
        m.add_command(label="Hide widget", command=lambda: app.toggle_widget(False))
        app._popup(m, e)

    def opacity(self, pct):
        self.app.mgr.settings["widget_alpha"] = pct
        self.app.mgr.save_settings()
        self.set_alpha()

    def update(self):
        if not self.shown or not self.cv:
            return
        p, items = PAL, self.app.mgr.items
        act = [d for d in items if d.status in ACTIVE]
        known = [d for d in act if d.size > 0]
        frac = (sum(min(d.done, d.size) for d in known) / sum(d.size for d in known)) if known else 0.0
        cv, (cx, cy, r) = self.cv, (28, 27, 17)
        cv.configure(bg=p["panel"], highlightbackground=p["border"])
        cv.delete("all")
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=p["grid"], width=5)
        if act and frac > 0:
            cv.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=-min(359.9, 360 * frac), style="arc", outline=p["accent"], width=5)
        cv.create_text(cx, cy, text=f"{int(frac * 100)}%" if known else ("\u2193" if act else "\u2713"), fill=p["fg"], font="AeroSmallBold")
        waiting = sum(d.status == "Queued" for d in items)
        cv.create_text(58, 19, anchor="w", text=(fmt_rate(sum(d.speed for d in act)) or "Starting...") if act else "Idle", fill=p["fg"], font="AeroBold")
        cv.create_text(58, 37, anchor="w", text=f"{len(act)} active" + (f", {waiting} queued" if waiting else ""), fill=p["muted"], font="AeroSmall")


# ============================ Updates: GitHub Releases ============================
UPDATE_API = "https://api.github.com/repos/alter-xsource404/AeroGrab-final-release/releases/latest"
UPDATE_PAGE = "https://github.com/alter-xsource404/AeroGrab-final-release/releases/latest"
UPDATE_HOSTS = ("github.com", "githubusercontent.com")  # an update is only ever downloaded from GitHub (https), including its CDN redirect
SETUP_WORDS = ("setup", "installer", "install")         # asset names containing one of these are the installer; the other .exe is the portable build
SETUP_ARGS = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/CLOSEAPPLICATIONS"]  # Inno Setup: small progress window, no questions. /VERYSILENT hides even that.


class UpdateError(Exception):
    pass


def parse_version(text):
    """'v1.6.10' -> (1, 6, 10). Anything after the numbers ('-beta') is ignored. None when there are no digits."""
    m = re.match(r"\s*[vV]?(\d+(?:\.\d+)*)", str(text or ""))
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_newer(latest, current=None):
    """True when `latest` is a higher version than `current` (1.6 == 1.6.0). Unreadable versions are never 'newer'."""
    a, b = parse_version(latest), parse_version(current or __version__)
    if not a or not b:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def install_kind(frozen=None, system=None, exe=None, listdir=os.listdir, env=None):
    """'installed' (set up by the Inno installer), 'portable' (a lone .exe) or 'manual' (source / macOS / Linux: no automatic install).
    The installer leaves its uninstaller (unins000.exe) next to aerograb.exe; a portable copy has none. AEROGRAB_UPDATE_KIND forces a kind (testing)."""
    env = os.environ if env is None else env
    forced = (env.get("AEROGRAB_UPDATE_KIND") or "").strip().lower()
    if forced in ("installed", "portable", "manual"):
        return forced
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not frozen or (system or platform.system()) != "Windows":
        return "manual"
    try:
        names = [n.lower() for n in listdir(os.path.dirname(exe or sys.executable))]
    except OSError:
        names = []
    return "installed" if any(re.fullmatch(r"unins\d+\.exe", n) for n in names) else "portable"


def pick_asset(assets, kind):
    """Choose the release file for this kind of install, by name: 'installed' -> the *setup* / *installer* .exe;
    'portable' -> the *portable* .exe (or, failing that, any .exe that is not an installer). None when nothing fits."""
    def name(a):
        return str(a.get("name") or "").lower()
    exes = [a for a in assets or [] if isinstance(a, dict) and name(a).endswith(".exe") and a.get("browser_download_url") and not name(a).startswith("unins")]
    is_setup = lambda a: any(w in name(a) for w in SETUP_WORDS)
    if kind == "installed":
        pool = [a for a in exes if is_setup(a)]
    elif kind == "portable":
        pool = [a for a in exes if "portable" in name(a)] or [a for a in exes if not is_setup(a)]
    else:
        return None
    pool.sort(key=lambda a: (not any(w in name(a) for w in ("win", "x64")), name(a)))
    return pool[0] if pool else None


def plain_notes(md, limit=6000):
    """GitHub release notes are Markdown; the dialog shows them as plain text."""
    out = []
    for ln in str(md or "").replace("\r\n", "\n").split("\n"):
        ln = re.sub(r"^\s{0,3}#{1,6}\s*", "", ln)
        ln = re.sub(r"^(\s*)[-*+]\s+", lambda m: m.group(1) + "\u2022 ", ln)
        ln = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", ln)
        out.append(re.sub(r"(\*\*|__|`)", "", ln).rstrip())
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "\u2026"
    return text or "No release notes were provided."


def parse_release(data, current=None, kind=None):
    """GitHub's 'latest release' JSON -> {version, notes, page, asset, kind, newer}. None for drafts / pre-releases."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    if not parse_version(tag):
        raise UpdateError("The latest release has no version number in its tag.")
    kind = kind or install_kind()
    page = data.get("html_url") or UPDATE_PAGE
    return {"version": ".".join(map(str, parse_version(tag))), "tag": tag, "notes": plain_notes(data.get("body")),
            "page": page if trusted_update_url(page) else UPDATE_PAGE, "kind": kind,
            "asset": pick_asset(data.get("assets"), kind), "newer": is_newer(tag, current)}


def fetch_latest_release(opener=None, url=UPDATE_API, timeout=15):
    """Asks GitHub for the latest release. Goes through AeroGrab's own connection layer, so the proxy settings apply."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with (opener or OPENER).open(req, timeout=timeout) as r:
            return json.loads(r.read(4_000_000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise UpdateError({404: "No release has been published yet.", 403: "GitHub is limiting requests right now. Try again later."}.get(e.code, f"GitHub answered HTTP {e.code}."))
    except (OSError, ValueError) as e:  # URLError, timeouts, bad JSON
        raise UpdateError(f"Could not reach GitHub ({getattr(e, 'reason', e)}).")


def check_for_update(opener=None, current=None, kind=None, url=UPDATE_API):
    """Network call. Returns parse_release()'s dict (its 'newer' says whether to offer it); raises UpdateError."""
    info = parse_release(fetch_latest_release(opener, url), current, kind)
    if info is None:
        raise UpdateError("The latest release is a draft or pre-release.")
    return info


def trusted_update_url(url):
    p = urllib.parse.urlparse(str(url or ""))
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == h or host.endswith("." + h) for h in UPDATE_HOSTS)


def folder_writable(folder):
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def download_update(asset, dest, progress=None, stop=None, opener=None, trusted=trusted_update_url):
    """Downloads the release file to `dest` (through a .part file) and checks it: right host, right size, the SHA-256 GitHub lists
    for the asset (when it lists one), and a Windows executable header. progress(done, total); set `stop` to cancel."""
    url = str(asset.get("browser_download_url") or "")
    if not trusted(url):
        raise UpdateError("The update is not hosted on GitHub; refusing to download it.")
    want_size, digest = int(asset.get("size") or 0), str(asset.get("digest") or "").lower()
    part, h, done = dest + ".part", hashlib.sha256(), 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream"})
        with (opener or OPENER).open(req, timeout=30) as r, open(part, "wb") as f:
            if not trusted(r.geturl()):
                raise UpdateError("The download was redirected away from GitHub; refusing it.")
            total = int(r.headers.get("Content-Length") or want_size or 0)
            while True:
                if stop is not None and stop.is_set():
                    raise UpdateError("Cancelled.")
                chunk = r.read(CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if (want_size and done != want_size) or (total and done != total):
            raise UpdateError(f"The download is incomplete ({done} of {total or want_size} bytes).")
        if digest.startswith("sha256:") and h.hexdigest() != digest[7:]:
            raise UpdateError("The download does not match GitHub's checksum; it was discarded.")
        with open(part, "rb") as f:
            if f.read(2) != b"MZ":
                raise UpdateError("The downloaded file is not a Windows program.")
        os.replace(part, dest)
        return dest
    except UpdateError:
        raise
    except OSError as e:
        raise UpdateError(f"Download failed: {getattr(e, 'reason', e)}")
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass


def _bat(path):
    return str(path).replace("%", "%%")  # a literal % in a path must be doubled inside a .bat file


def portable_script(target, new):
    """Batch file for the portable build. AeroGrab has to be gone before its .exe can be overwritten, so it keeps retrying the swap
    (up to ~90 s), then starts the new copy. If it never succeeds it removes the download and starts the old copy again."""
    return "\r\n".join([
        "@echo off", "chcp 65001 >nul", f'set "TARGET={_bat(target)}"', f'set "NEW={_bat(new)}"', "set /a TRIES=0", ":swap",
        'move /y "%NEW%" "%TARGET%" >nul 2>&1', "if not errorlevel 1 goto done", "set /a TRIES+=1", "if %TRIES% GEQ 90 goto fail",
        "ping -n 2 127.0.0.1 >nul", "goto swap", ":fail", 'del "%NEW%" >nul 2>&1', ":done", 'start "" "%TARGET%"',
        '(goto) 2>nul & del "%~f0"', ""])


def installer_script(setup, target, args=None):
    """Batch file for the installed build: wait for AeroGrab to exit, run the installer silently, delete it, start AeroGrab again."""
    return "\r\n".join([
        "@echo off", "chcp 65001 >nul", f'set "SETUP={_bat(setup)}"', f'set "TARGET={_bat(target)}"', "ping -n 4 127.0.0.1 >nul",
        'start "" /wait "%SETUP%" ' + " ".join(args or SETUP_ARGS), 'del "%SETUP%" >nul 2>&1', 'start "" "%TARGET%"', '(goto) 2>nul & del "%~f0"', ""])


def launch_script(script, popen=subprocess.Popen):
    """Runs a .bat in the background, without a console window, and independent of AeroGrab (which is about to quit)."""
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")  # the new copy must unpack itself instead of reusing this one's temp folder
    env.pop("_MEIPASS2", None)
    popen(["cmd.exe", "/c", script], creationflags=0x08000000 | 0x00000200,  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
          close_fds=True, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stage_path(kind, asset, exe=None):
    """Where the update is downloaded to. Portable: next to the running .exe (so the final swap is one atomic rename on the same drive)."""
    if kind == "portable":
        exe = exe or sys.executable
        if not folder_writable(os.path.dirname(exe)):
            raise UpdateError("AeroGrab's folder is write-protected, so it can't replace itself there.\nMove it to a normal folder, or download the new version by hand.")
        return exe + ".new"
    safe = re.sub(r"[^\w.\- ]", "_", os.path.basename(str(asset.get("name") or "aerograb-Setup.exe")))
    folder = os.path.join(tempfile.gettempdir(), "aerograb-update")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, safe)


def apply_update(kind, downloaded, exe=None, launcher=launch_script):
    """Writes the helper script and starts it. The caller must quit AeroGrab right afterwards."""
    if not getattr(sys, "frozen", False) and exe is None:
        raise UpdateError("Only the packaged .exe can update itself.")
    exe = exe or sys.executable
    text = portable_script(exe, downloaded) if kind == "portable" else installer_script(downloaded, exe)
    script = os.path.join(tempfile.mkdtemp(prefix="aerograb-update-"), "update.bat")
    with open(script, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    launcher(script)
    return script


class App:
    """The main window, laid out like IDM's classic interface: menu bar, icon toolbar, a navigation tree on the left
    (All Downloads > categories, Unfinished, Finished, Grabber projects, Queues) and the download list on the right."""

    def __init__(self, port=API_PORT, minimized=False, single=None):
        _load_tk()
        self.port, self.minimized, self.single = port, minimized, single  # single: the SingleInstance this process owns (None in tests)
        self.mgr = Manager()
        st = self.mgr.settings
        enable_dpi_awareness()   # Windows: sharp at 125 / 150 / 200 % scaling (must happen before the first window exists)
        self.root = root = tk.Tk()
        root.title(APP_TITLE)
        self.theme = Theme(root, root.winfo_fpixels("1i") / 96.0)   # the design system: fonts, ttk styles, icons (aerograb_theme.py)
        _UI["theme"] = self.theme
        self.px, self.style = self.theme.px, self.theme.style
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(self.px(1220), sw - 40)}x{min(self.px(700), sh - 90)}")   # fits a 1366x768 screen at any scaling
        root.minsize(min(self.px(860), sw - 40), min(self.px(480), sh - 90))
        try:  # window / taskbar icon (embedded, so it also works from a single-file build)
            root._icon = tk.PhotoImage(data=ICON_B64)
            root.iconphoto(True, root._icon)
        except tk.TclError:
            pass
        self._mode_seen, self._mode_check = "dark", 0.0
        self._row_cache, self._status_imgs, self._open_menu, self._menu_icons, self._hover_row = {}, {}, None, {}, None
        self._elide_cache, self._name_w, self._bars, self._bar_pool, self._idle, self._ph = {}, 0, {}, [], {}, True
        self._tb_compact, self._tb_full_w = False, 1
        self.sounds, self.sound_seen = SoundPlayer(st, focused=self._has_focus), {}
        self.sounds.fallback = root.bell  # no sound player or sound file on this machine: at least beep
        root.bind_class("Toplevel", "<Map>", self._style_toplevel, add="+")   # every dialog gets the themed title bar the moment it appears
        self.apply_theme()

        self.folder = tk.StringVar(value=st.get("folder") or os.path.join(os.path.expanduser("~"), "Downloads"))
        st["folder"] = self.folder.get()
        self.conns = tk.IntVar(value=int(st.get("connections") or 8))
        self.limit_var = tk.IntVar(value=int(st.get("limit_kb") or 0))
        self.limit_var.trace_add("write", self._on_limit)
        self.flt = tk.StringVar(value="all")  # "all" | "unfinished" | "finished" | "cat:X" | "queue:X" | "project:X" | "queues" | "projects"
        self.sort = ("", False)
        self.show_side, self.show_toolbar, self.show_status, self.show_map = (tk.BooleanVar(value=True) for _ in range(4))
        self.tray, self.last_tip, self.seen, self.hint_shown = None, "", {}, False
        self.side_map = {}      # navigation tree row id -> (label, filter)
        self.menu_rules = []    # (menu, index, rule): which entries are greyed out for the current selection
        self.note, self._quiet = ("", 0), False
        self.captured, self.pending_urls, self.pwins = queue.Queue(), set(), {}  # links from the browser awaiting confirmation; open confirm dialogs; open progress windows
        for d in self.mgr.items:
            d.announced = d._threat_told = d.status == "Completed"  # only downloads that finish during this session pop up "Download complete" (or a threat warning)
        self.mgr.scanner_on = True  # finished downloads are checked by the installed antivirus (Options > Extras)
        self.scan_watch = []  # downloads whose manual 'Scan for viruses' result is still to be shown
        self.clips, self._clip_last, self._clip_check = ClipHistory(os.path.join(CFG_DIR, "clipboard.json")), None, 0.0
        self.show_widget = tk.BooleanVar(value=bool(st.get("widget_on")))
        self.widget = FloatingWidget(self)
        self.api_srv = start_api(self.mgr, lambda: (self.folder.get(), self.conns.get()), port, confirm=self._capture)
        self.update_q, self.update_info, self._upd_busy, self._upd_pending, self._upd_win = queue.Queue(), None, False, False, None  # update check (GitHub Releases)
        self.build_menu()
        self.build_ui()
        self.build_context_menus()
        self.bind_keys()
        self.rebuild_side()
        root.protocol("WM_DELETE_WINDOW", self.request_close)

    # ------------------------------------------------------------------ appearance
    def _has_focus(self):
        try:
            return self.root.state() in ("normal", "zoomed") and self.root.focus_displayof() is not None
        except tk.TclError:
            return False

    def apply_theme(self):
        """Dark / Light / follow-the-system, plus the accent colour. Safe to call at any time and as often as you like (the View menu, the header
        button and Options all call it): it only re-colours the interface - the download engine, queues and settings are not touched."""
        st, root = self.mgr.settings, self.root
        skin = str(st.get("skin") or "default").lower()
        skin = skin if skin in SKINS else "default"
        mode = SKINS[skin][0] if skin != "default" else resolve_mode(st.get("theme", "dark"))  # a skin brings its own light / dark
        p = make_palette(mode, valid_hex(st.get("accent")) or DEFAULT_ACCENT, skin)
        self._mode_seen = mode
        self.theme.apply(p)
        root.configure(bg=p["bg"])
        self.theme.repaint(root)
        style_titlebar(root, p)
        for w in root.winfo_children():
            if w.winfo_class() == "Toplevel":
                self._style_toplevel(w)
        if hasattr(self, "tree"):
            self.refresh_visuals()

    def _style_toplevel(self, e):
        w = getattr(e, "widget", e)
        try:
            if w.winfo_class() == "Toplevel" and not w.overrideredirect():
                style_titlebar(w, self.theme.p)
        except (tk.TclError, AttributeError):
            pass

    def icon(self, name, size=20, **kw):
        return self.theme.icon(name, size, **kw)

    def set_theme(self, mode):
        """Dark or Light (or 'system'), chosen from the header button, the View menu or Options. Saved with the other settings, applied at once."""
        st = self.mgr.settings
        st["theme"] = mode
        st["skin"] = "default"   # a skin would override the choice
        self.mgr.save_settings()
        self.apply_theme()

    def toggle_theme(self):
        self.set_theme("light" if self.theme.p["mode"] == "dark" else "dark")

    def follow_system_theme(self):
        if self.mgr.settings.get("theme", "dark") == "system" and self.mgr.settings.get("skin", "default") == "default" and time.time() - self._mode_check > 30:
            self._mode_check = time.time()
            if resolve_mode("system") != self._mode_seen:
                self.apply_theme()

    # ------------------------------------------------------------------ sounds
    def collect_sounds(self, queue_finished):
        """Work out what just happened (finished / failed / queue done) and let the SoundPlayer pick one sound for it."""
        ev = {"all_done"} if queue_finished else set()
        for d in self.mgr.items:
            key = (d.status, d.verified, d.scan)
            prev, self.sound_seen[id(d)] = self.sound_seen.get(id(d)), key
            if prev is None or prev == key:
                continue
            if d.status == "Completed" and d.scan == "infected" and prev[2] != "infected":
                ev.add("error")
            if d.status == "Completed":
                if d.checksum:  # with a checksum the result is known only after the hash check
                    if d.verified == "ok" and prev[1] != "ok":
                        ev.add("complete")
                    elif d.verified in ("bad", "missing") and prev[1] != d.verified:
                        ev.add("error")
                elif prev[0] != "Completed":
                    ev.add("complete")
            elif d.status == "Error" and prev[0] != "Error" and not self.mgr.will_retry(d):  # a failure that is about to be retried stays quiet
                ev.add("error")
        if ev:
            self.sounds.flush(ev)

    def test_sound(self, event, custom=""):
        if not run_sound(sound_plan(event, custom=custom)):
            self.root.bell()

    # ------------------------------------------------------------------ small helpers
    def _on_limit(self, *_):
        try:
            self.mgr.set_limit_kb(self.limit_var.get())
        except tk.TclError:  # box is empty or mid-edit
            pass

    def selected(self):
        return [self.mgr.items[int(i)] for i in self.tree.selection() if int(i) < len(self.mgr.items)]

    def cur_queue(self):
        f = self.flt.get()
        return f[6:] if f.startswith("queue:") else MAIN_QUEUE

    def info(self, title, text, parent=None):
        messagebox.showinfo(title, text, parent=parent or self.root)

    # ------------------------------------------------------------------ menu bar
    def build_menu(self):
        """The menu *model* (labels, commands, shortcuts, icons). Windows draws a native menu bar in plain white no matter what colours it is given,
        so the visible bar is built from these menus by build_menubar() and the model itself is never attached to the window."""
        bar = tk.Menu(self.root, tearoff=0)
        self.menubar = bar
        self.theme_var = tk.StringVar(value=self.mgr.settings.get("theme", "dark"))

        def menu(label, underline=0):
            m = tk.Menu(bar, tearoff=0, postcommand=self.update_state)
            bar.add_cascade(label=label, menu=m, underline=underline)
            return m

        def pic(m, icon):
            if not icon:
                return {}
            self._menu_icons[(str(m), m.index("end"))] = icon
            return dict(image=self.theme.padded_icon(icon, 16), compound="left")

        def item(m, label, cmd, accel=None, need=None, icon=None):
            m.add_command(label=label, command=cmd, accelerator=accel)
            if icon:
                m.entryconfig(m.index("end"), **pic(m, icon))
            if need:
                self.menu_rules.append((m, m.index("end"), need))

        def cascade(m, label, sub, icon, need=None):
            m.add_cascade(label=label, menu=sub)
            m.entryconfig(m.index("end"), **pic(m, icon))
            if need:
                self.menu_rules.append((m, m.index("end"), need))

        tasks = menu("Tasks")
        item(tasks, "Add new download...", self.add_dialog, "Ctrl+N", icon="add")
        item(tasks, "Add batch download from clipboard", self.add_from_clipboard, icon="paste")
        item(tasks, "Clipboard history...", self.clipboard_dialog, icon="clip")
        item(tasks, "Run site grabber...", self.grabber_dialog, icon="grabber")
        tasks.add_separator()
        item(tasks, "Export download list...", self.export_list, icon="export")
        item(tasks, "Import download list...", self.import_list, icon="import")
        tasks.add_separator()
        item(tasks, "Exit", self.on_close, "Alt+F4", icon="exit")

        f = menu("File")
        item(f, "Open", self.open_file, "Enter", "done", icon="open")
        item(f, "Open folder", self.open_folder, None, "sel", icon="open_folder")
        item(f, "Move/Rename...", self.rename_file, "F2", "done1", icon="rename")
        item(f, "Redownload", self.redownload, None, "sel", icon="redownload")
        item(f, "Verify checksum / hashes...", self.hashes_selected, None, "done1", icon="hash")
        item(f, "Scan for viruses", self.scan_selected, None, "done", icon="scan")
        f.add_separator()
        item(f, "Properties...", self.properties_dialog, "Alt+Enter", "sel1", icon="properties")
        item(f, "Copy address", self.copy_address, "Ctrl+C", "sel", icon="copy")

        d = menu("Downloads")
        item(d, "Resume", self.resume, "Ctrl+R", "resumable", icon="resume")
        item(d, "Stop", self.stop, "Ctrl+S", "active", icon="stop")
        item(d, "Stop All", self.stop_all, None, "anyactive", icon="stopall")
        d.add_separator()
        item(d, "Delete", self.delete, "Del", "sel", icon="delete")
        item(d, "Delete completed", self.delete_completed, None, "anydone", icon="delc")
        d.add_separator()
        self.menu_cat = tk.Menu(d, tearoff=0, postcommand=lambda: self._fill_cat_menu(self.menu_cat))
        cascade(d, "Move to category", self.menu_cat, "to_category", "sel")
        self.menu_que = tk.Menu(d, tearoff=0, postcommand=lambda: self._fill_queue_menu(self.menu_que))
        cascade(d, "Move to queue", self.menu_que, "to_queue", "sel")
        d.add_separator()
        item(d, "Start queue", self.start_queue, icon="startq")
        item(d, "Stop queue", self.stop_queue, icon="stopq")
        item(d, "New queue...", self.new_queue, icon="new_queue")
        d.add_separator()
        item(d, "Speed limiter...", self.speed_dialog, icon="limiter")
        item(d, "Limit selected downloads...", self.limit_selected, None, "sel", icon="limiter")
        item(d, "Scheduler...", self.scheduler_dialog, icon="scheduler")
        item(d, "Categories...", self.categories_dialog, icon="categories")
        d.add_separator()
        item(d, "Options...", self.options_dialog, icon="options")

        v = menu("View")
        for label, var, cmd in (("Toolbar", self.show_toolbar, self.apply_layout), ("Categories pane", self.show_side, self.apply_layout),
                                ("Segment map", self.show_map, self.apply_layout), ("Status bar", self.show_status, self.apply_layout)):
            v.add_checkbutton(label=label, variable=var, command=cmd)
        v.add_separator()
        themes = tk.Menu(v, tearoff=0)
        for label, key, icon in (("Dark", "dark", "moon"), ("Light", "light", "sun"), ("Follow system", "system", "monitor")):
            themes.add_radiobutton(label=label, variable=self.theme_var, value=key, command=lambda k=key: self.set_theme(k))
        cascade(v, "Theme", themes, "moon")
        v.add_checkbutton(label="Floating widget", variable=self.show_widget, command=lambda: self.toggle_widget(self.show_widget.get()))
        item(v, "Customize toolbar...", self.customize_toolbar, icon="sliders")
        v.add_separator()
        sortm = tk.Menu(v, tearoff=0)
        for key, title, _ in COLUMNS:
            sortm.add_command(label=title, command=lambda k=key: self.sort_by(k, toggle=False))
        sortm.add_separator()
        sortm.add_command(label="Original order", command=lambda: self.sort_by("", toggle=False))
        cascade(v, "Sort by", sortm, "sort")
        item(v, "Refresh", self.tick_once, "F5", icon="refresh")

        h = menu("Help")
        item(h, "Quick help", self.help_dialog, icon="help")
        item(h, "Browser extension setup...", self.pairing_dialog, icon="puzzle")
        item(h, "Keyboard shortcuts", self.shortcuts_dialog, icon="keyboard")
        item(h, "Check for updates...", lambda: self.start_update_check(manual=True), icon="update")
        h.add_separator()
        item(h, "About AeroGrab", self.about_dialog, icon="about")

        r = menu("Registration")
        item(r, "Registration status...", self.registration_dialog, icon="registration")
        item(r, "License (MIT)...", self.license_dialog, icon="license")

    # ------------------------------------------------------------------ the visible menu bar
    def build_menubar(self, parent):
        """A themed menu bar made of flat labels that open the menus of the model. Hover switches between menus; Alt+letter opens one."""
        fr = tk.Frame(parent, bd=0, highlightthickness=0)
        fr._keep_bg = True
        self.menubar_frame, self.menu_labels, self._menu_hot = fr, [], None
        for i in range(self.menubar.index("end") + 1):
            label = self.menubar.entrycget(i, "label")
            m = self.root.nametowidget(self.menubar.entrycget(i, "menu"))
            b = tk.Label(fr, text=label, padx=self.px(11), pady=self.px(6), bd=0)
            b._keep_bg = True
            b.pack(side="left", padx=1)
            b.bind("<Button-1>", lambda e, b=b, m=m: self.open_menu(b, m))
            b.bind("<Enter>", lambda e, b=b, m=m: self._menu_enter(b, m))
            b.bind("<Leave>", lambda e, b=b: self._menu_leave(b))
            m.bind("<Unmap>", lambda e, b=b: self._menu_closed(b), add="+")
            self.menu_labels.append((b, m))
            for ch in {label[0].lower(), label[0].upper()}:
                self.root.bind(f"<Alt-{ch}>", lambda e, b=b, m=m: self.open_menu(b, m))
        self.paint_menubar()
        return fr

    def paint_menubar(self):
        p = self.theme.p
        self.menubar_frame.configure(bg=p["bg"])
        for b, m in self.menu_labels:
            on = self._open_menu and self._open_menu[0] is b
            hot = self._menu_hot is b
            b.configure(bg=p["selected"] if on else p["hover"] if hot else p["bg"], fg=p["fg"], font="TkDefaultFont")

    def _menu_enter(self, b, m):
        self._menu_hot = b
        if self._open_menu and self._open_menu[0] is not b:   # a menu is open: moving to a neighbour switches to it, like a native menu bar
            self.close_menu()
            self.open_menu(b, m)
        self.paint_menubar()

    def _menu_leave(self, b):
        if self._menu_hot is b:
            self._menu_hot = None
        self.paint_menubar()

    def open_menu(self, b, m):
        if self._open_menu and self._open_menu[0] is b:
            return self.close_menu()
        self.close_menu()
        self._open_menu = (b, m)
        self.paint_menubar()
        try:
            m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            try:
                m.grab_release()
            except tk.TclError:
                pass
            if platform.system() == "Windows":   # tk_popup blocks there: the menu is closed when it returns
                self._menu_closed(b)

    def close_menu(self):
        if self._open_menu:
            b, m = self._open_menu
            self._open_menu = None
            try:
                m.unpost()
            except tk.TclError:
                pass
            self.paint_menubar()

    def _menu_closed(self, b):
        if self._open_menu and self._open_menu[0] is b:
            self._open_menu = None
            self.paint_menubar()

    def refresh_menu_icons(self):
        """Menus keep their pictures after a theme change, tinted for the new palette; entries that are greyed out get the dimmed picture."""
        fl = self.flags() if hasattr(self, "tree") else {}
        off = {}
        for m, idx, rule in self.menu_rules:
            off.setdefault(str(m), {})[idx] = not fl.get(rule, True)
        for (mname, idx), icon in self._menu_icons.items():
            try:
                m = self.root.nametowidget(mname)
                dim = off.get(mname, {}).get(idx, False)
                m.entryconfig(idx, image=self.theme.padded_icon(icon, 16, color=self.theme.p["disabled"]) if dim else self.theme.padded_icon(icon, 16))
            except (tk.TclError, KeyError):
                pass

    # ------------------------------------------------------------------ window layout
    def build_ui(self):
        root, px, p = self.root, self.px, self.theme.p
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)
        # ---- header: brand mark + name + version, the menu bar, then search and the theme switch on the right
        self.brand = ttk.Frame(root, padding=(px(12), px(6), px(12), px(4)))
        self.brand.grid(row=0, column=0, sticky="ew")
        self.logo_img = tk.PhotoImage(data=BRAND_B64[64 if self.theme.scale >= 1.5 else 32])
        if self.theme.scale >= 1.5:
            self.logo_img = self.logo_img.subsample(2)   # 64 px source drawn at 32 px: crisp on high-DPI screens
        ttk.Label(self.brand, image=self.logo_img).pack(side="left", padx=(0, px(8)))
        ttk.Label(self.brand, text=APP_NAME, style="Brand.TLabel").pack(side="left")
        ttk.Label(self.brand, text=f"v{__version__}", style="BrandVer.TLabel").pack(side="left", padx=(px(6), 0), pady=(px(3), 0))
        self.build_menubar(self.brand).pack(side="left", padx=(px(20), 0))
        self.theme_btn = ttk.Button(self.brand, style="Tool.TButton", command=self.toggle_theme, takefocus=True)
        self.theme_btn.pack(side="right")
        Tip(self.theme_btn, lambda: "Switch to the Light theme" if self.theme.p["mode"] == "dark" else "Switch to the Dark theme")
        self.search = tk.StringVar()
        self.search_box = tk.Frame(self.brand, highlightthickness=1, bd=0)
        self.search_box._keep_bg = True
        self.search_icon = tk.Label(self.search_box, bd=0)
        self.search_icon._keep_bg = True
        self.search_icon.pack(side="left", padx=(px(8), 0))
        self.search_entry = tk.Entry(self.search_box, textvariable=self.search, width=20, bd=0, highlightthickness=0, relief="flat")
        self.search_entry.pack(side="left", padx=px(6), pady=px(5), fill="x", expand=True)
        self.search_box.pack(side="right", padx=(0, px(10)))
        self.search_entry.bind("<FocusIn>", lambda e: self._search_focus(True))
        self.search_entry.bind("<FocusOut>", lambda e: self._search_focus(False))
        self.search_entry.bind("<Escape>", lambda e: (self.search.set(""), self.tree.focus_set()))
        self.search.trace_add("write", lambda *_: self._search_changed())
        Tip(self.search_entry, "Search downloads by name, address or description")
        self.search.set("Search downloads")
        # ---- toolbar: big tinted icon above the label, flat rounded buttons, grouped by separators
        self.toolbar = ttk.Frame(root)
        self.toolbar.grid(row=1, column=0, sticky="ew")
        self.toolbar_inner = ttk.Frame(self.toolbar, padding=(px(8), px(3)))
        self.toolbar_inner.pack(fill="x")
        ttk.Separator(self.toolbar, orient="horizontal").pack(fill="x")
        self.tbtn = {}
        self.rebuild_toolbar()
        # ---- navigation tree (left) + download list (right) in a resizable split
        self.body = ttk.PanedWindow(root, orient="horizontal")
        self.body.grid(row=2, column=0, sticky="nsew", padx=px(8), pady=(px(6), px(4)))
        self.side_frame = ttk.Frame(self.body, style="Side.TFrame")
        self.side = ttk.Treeview(self.side_frame, show="tree", columns=("n",), selectmode="browse", style="Side.Treeview", height=6)
        self.side.column("#0", width=px(212), minwidth=px(140))
        self.side.column("n", width=px(46), minwidth=px(36), anchor="e", stretch=False)
        self.side.pack(fill="both", expand=True, padx=(px(4), 0), pady=px(4))
        self.side.bind("<<TreeviewSelect>>", self.on_side)
        self.list_frame = ttk.Frame(self.body, style="Surface.TFrame")
        self.list_frame.grid_rowconfigure(0, weight=1)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.list_frame, columns=[c[0] for c in COLUMNS], displaycolumns=[c[0] for c in COLUMNS if c[0] != "name"],
                                 show="tree headings", selectmode="extended", style="Main.Treeview", height=6)
        anchors = {"q": "center", "size": "e", "left": "e", "rate": "e"}
        for key, title, w in COLUMNS:
            col = "#0" if key == "name" else key
            self.tree.heading(col, text=title, command=lambda k=key: self.sort_by(k), anchor="w" if key not in anchors else anchors[key])
            self.tree.column(col, width=px(w), minwidth=px(30), anchor=anchors.get(key, "w"), stretch=key in ("name", "desc"))
        self.tree.heading("name", text="File Name")
        self.tree.column("#0", width=px(230), minwidth=px(120))
        self.vsb = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self._yscrolled, xscrollcommand=self._xscrolled)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: (self.update_state(), self.after_idle_once(self._place_bars)))
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Motion>", self._row_hover)
        self.tree.bind("<Leave>", lambda e: self._row_hover(None))
        self.tree.bind("<Configure>", self._tree_resized, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after_idle_once(self._elide_all), add="+")
        self.tree.bind("<MouseWheel>", lambda e: self.after_idle_once(self._place_bars), add="+")
        self.body.add(self.side_frame, weight=0)
        self.body.add(self.list_frame, weight=1)
        # ---- the segment map of the selected download (a slim strip under the list; View > Segment map)
        self.gframe = ttk.Frame(root, padding=(px(12), px(2), px(12), px(4)))
        self.gframe.grid(row=3, column=0, sticky="ew")
        self.gtitle = ttk.Label(self.gframe, text="", style="Small.TLabel", anchor="w")
        self.gtitle.pack(fill="x")
        self.mapcv = tk.Canvas(self.gframe, height=px(12), bg=p["map_bg"], highlightthickness=0)
        self.mapcv._keep_bg = True
        self.mapcv.pack(fill="x", pady=(px(3), 0))
        # ---- status bar
        self.status = ttk.Label(root, text="", anchor="w", style="Status.TLabel", padding=(px(14), px(6)))
        self.status.grid(row=4, column=0, sticky="ew")
        self.apply_layout()
        self.refresh_visuals()
        root.bind("<Configure>", lambda e: self.after_idle_once(self._fit_toolbar) if e.widget is root else None, add="+")

    def after_idle_once(self, fn):
        """Run fn once after the pending events, however many times this is asked for in between (scrolling, resizing, dragging)."""
        if fn not in self._idle:
            self._idle[fn] = self.root.after(60, lambda: (self._idle.pop(fn, None), fn()))

    def refresh_visuals(self):
        """Everything that carries a colour or a picture and was built before the palette changed: called after every theme switch."""
        p, th = self.theme.p, self.theme
        self._status_imgs = {k: th.icon(k, 18) for k in ("st_done", "st_active", "st_paused", "st_error", "st_queued", "st_wait")}
        self._row_cache.clear()
        for tag, kw in (("odd", {"background": p["zebra"]}), ("hover", {"background": p["hover"]}), ("error", {"foreground": p["danger"]}),
                        ("threat", {"foreground": p["danger"]})):
            self.tree.tag_configure(tag, **kw)
        self.paint_menubar()
        self.paint_search()
        self.theme_btn.configure(image=th.icon("sun" if p["mode"] == "dark" else "moon", 20, tone="icon"))
        self.search_icon.configure(image=th.icon("search", 16, tone="muted"))
        self.theme_var.set(self.mgr.settings.get("theme", "dark") if self.mgr.settings.get("skin", "default") == "default" else self.theme_var.get())
        self.mapcv.configure(bg=p["map_bg"])
        self.rebuild_toolbar()
        self.rebuild_side()
        self.refresh_menu_icons()
        self.draw_list()
        self.redraw_segments()
        self._elide_all()

    def paint_search(self):
        p = self.theme.p
        focus = self.root.focus_get() is self.search_entry
        self.search_box.configure(bg=p["surface"], highlightbackground=p["border_strong"], highlightcolor=p["accent"], highlightthickness=1)
        self.search_box.configure(highlightbackground=p["accent"] if focus else p["border_strong"])
        self.search_icon.configure(bg=p["surface"])
        self.search_entry.configure(bg=p["surface"], fg=p["muted"] if self._ph else p["fg"], insertbackground=p["fg"], selectbackground=p["accent_soft"], selectforeground=p["fg"], disabledbackground=p["surface"])

    def _search_focus(self, focused):
        if focused and self._ph:
            self._ph = False
            self.search.set("")
        elif not focused and not self.search.get():
            self._ph = True
            self.search.set("Search downloads")
        self.paint_search()

    def _search_changed(self):
        self.after_idle_once(self.draw_list)

    def apply_layout(self):
        if self.show_toolbar.get():
            self.toolbar.grid()
        else:
            self.toolbar.grid_remove()
        if self.show_map.get():
            self.gframe.grid()
        else:
            self.gframe.grid_remove()
        if self.show_status.get():
            self.status.grid()
        else:
            self.status.grid_remove()
        shown = str(self.side_frame) in [str(p) for p in self.body.panes()]
        if self.show_side.get() and not shown:
            self.body.insert(0, self.side_frame, weight=0)
        elif not self.show_side.get() and shown:
            self.body.forget(self.side_frame)

    # ------------------------------------------------------------------ navigation tree
    CAT_ICONS = {"general": "cat_general", "compressed": "cat_compressed", "documents": "cat_documents", "music": "cat_music", "video": "cat_video",
                 "images": "cat_images", "programs": "cat_programs"}

    def rebuild_side(self):
        want = self.flt.get()
        self.side.delete(*self.side.get_children())
        self.side_map.clear()
        self._side_imgs = {}

        def add(parent, iid, label, flt, icon):
            self._side_imgs[iid] = self.icon(icon, 18)
            self.side.insert(parent, "end", iid=iid, text=" " + label, values=("",), image=self._side_imgs[iid], open=True)
            self.side_map[iid] = (label, flt)
        add("", "all", "All Downloads", "all", "t_all")
        for n, c in enumerate(self.mgr.settings["categories"]):
            add("all", f"c:{n}", c["name"], "cat:" + c["name"], self.CAT_ICONS.get(c["name"].strip().lower(), "t_folder"))
        add("", "unfinished", "Unfinished", "unfinished", "t_unfinished")
        add("", "finished", "Finished", "finished", "t_finished")
        add("", "projects", "Grabber projects", "projects", "t_grabber")
        for n, p in enumerate(self.mgr.projects()):
            add("projects", f"p:{n}", p, "project:" + p, "t_folder")
        add("", "queues", "Queues", "queues", "t_queue")
        for n, q in enumerate(self.mgr.settings["queues"]):
            add("queues", f"q:{n}", q, "queue:" + q, "t_queue_item")
        iid = next((i for i, (_, f) in self.side_map.items() if f == want), "all")
        self.flt.set(self.side_map[iid][1])
        self._select_side(iid)
        self.update_side()

    def _select_side(self, iid):
        self._quiet = True
        self.side.selection_set(iid)
        self._quiet = False

    def update_side(self):
        for iid, (label, f) in self.side_map.items():
            n = sum(matches_filter(d, f) for d in self.mgr.items)
            if self.side.set(iid, "n") != str(n):   # only touch rows whose count changed
                self.side.set(iid, "n", n)

    def on_side(self, _=None):
        sel = self.side.selection()
        if getattr(self, "_quiet", False) or not sel or sel[0] not in self.side_map:
            return
        self.flt.set(self.side_map[sel[0]][1])
        self.draw_list()
        self.update_state()

    # ------------------------------------------------------------------ download list
    def sort_by(self, col, toggle=True):
        old, rev = self.sort
        self.sort = (col, (not rev) if (toggle and col == old and col) else False)
        for key, title, _ in COLUMNS:
            arrow = (" \u25b2" if not self.sort[1] else " \u25bc") if key == self.sort[0] else ""
            self.tree.heading("#0" if key == "name" else key, text=title + arrow)
            if key == "name":
                self.tree.heading("name", text=title + arrow)
        self.draw_list()

    def row_values(self, d, qpos):
        return (d.label, qpos.get(id(d), ""), human(d.size) if d.size > 0 else "", status_text(d), fmt_left(d.eta_sec),
                fmt_rate(d.speed) if d.status in ACTIVE else "", fmt_when(d.last_try), d.desc)

    STATUS_ICONS = {"Completed": "st_done", "Downloading": "st_active", "Connecting": "st_active", "Paused": "st_paused", "Error": "st_error", "Queued": "st_queued"}

    def _search_hit(self, d, q):
        return q in d.label.lower() or q in (d.url or "").lower() or q in (d.desc or "").lower()

    def _name_px(self):
        try:
            return max(self.px(40), int(self.tree.column("#0", "width")) - self.px(40))   # minus the status icon and the cell padding
        except (tk.TclError, ValueError):
            return self.px(200)

    def _elide(self, text, width):
        """`text` cut to `width` pixels with an ellipsis (Tk would just clip it at the cell edge). Results are cached per width."""
        key = (text, width)
        hit = self._elide_cache.get(key)
        if hit is not None:
            return hit
        font = self.theme.fonts["body"]
        if font.measure(text) <= width:
            out = text
        else:
            lo, hi = 1, len(text)
            while lo < hi:   # the longest prefix that still fits together with the ellipsis
                mid = (lo + hi + 1) // 2
                if font.measure(text[:mid].rstrip() + "\u2026") <= width:
                    lo = mid
                else:
                    hi = mid - 1
            out = text[:lo].rstrip() + "\u2026"
        if len(self._elide_cache) > 40000:
            self._elide_cache.clear()
        self._elide_cache[key] = out
        return out

    def _elide_all(self):
        w = self._name_px()
        if w != self._name_w:
            self._name_w = w
            self._row_cache.clear()
            self.draw_list()

    def _tree_resized(self, e=None):
        self.after_idle_once(self._elide_all)
        self.after_idle_once(self._place_bars)

    def _yscrolled(self, a, b):
        self.vsb.set(a, b)
        self.after_idle_once(self._place_bars)

    def _xscrolled(self, a, b):
        if float(a) <= 0.0 and float(b) >= 1.0:   # everything fits: no horizontal bar
            self.hsb.grid_remove()
        else:
            self.hsb.grid()
        self.hsb.set(a, b)
        self.after_idle_once(self._place_bars)

    def _row_hover(self, e):
        iid = (self.tree.identify_row(e.y) if e else "") or None
        if iid == self._hover_row:
            return
        old, self._hover_row = self._hover_row, iid
        for r in (old, iid):
            if r and self.tree.exists(r) and r in self._row_cache:
                self.tree.item(r, tags=self._row_cache[r][2] + (("hover",) if r == self._hover_row else ()))

    def draw_list(self):
        qpos = queue_positions(self.mgr.items)
        q = "" if self._ph else self.search.get().strip().lower()
        flt = self.flt.get()
        rows = [(i, d) for i, d in enumerate(self.mgr.items) if matches_filter(d, flt) and (not q or self._search_hit(d, q))]
        col, rev = self.sort
        if col:
            rows.sort(key=lambda t: sort_key(t[1], col, qpos), reverse=rev)
        ids = [str(i) for i, _ in rows]
        same = list(self.tree.get_children()) == ids   # same rows in the same order: update in place, so selection and scroll position stay
        sel = self.tree.selection()
        if not same:
            self.tree.delete(*self.tree.get_children())
            self._row_cache.clear()
        width, hot, imgs, bars = self._name_px(), self._hover_row, self._status_imgs, {}
        for n, (i, d) in enumerate(rows):
            iid, vals = str(i), self.row_values(d, qpos)
            icon = self.STATUS_ICONS.get(d.status, "st_wait")
            bad = d.status == "Error" or (d.status == "Completed" and getattr(d, "scan", "") == "infected")
            if bad and d.status == "Completed":
                icon = "st_error"
            base = (("odd",) if n % 2 else ()) + (("error",) if bad else ())
            key = (vals, icon, base, self._elide(vals[0], width))
            if not same:
                self.tree.insert("", "end", iid=iid, text=" " + key[3], values=vals, image=imgs[icon], tags=base + (("hover",) if iid == hot else ()))
            elif self._row_cache.get(iid) != key:
                self.tree.item(iid, text=" " + key[3], values=vals, image=imgs[icon], tags=base + (("hover",) if iid == hot else ()))
            self._row_cache[iid] = key
            if d.status != "Completed" and d.size > 0 and d.done > 0:   # a thin progress bar under the status text
                tone = {"Downloading": "accent", "Connecting": "accent", "Error": "danger"}.get(d.status, "muted")
                bars[iid] = (max(0.0, min(1.0, d.percent / 100.0)), tone, n % 2 == 1)
        if not same:
            for i in sel:
                if self.tree.exists(i):
                    self.tree.selection_add(i)
        self._bars = bars
        self.after_idle_once(self._place_bars)

    # ---- progress bars: small canvases laid over the Status cells of the rows that are in progress (pooled, only for rows on screen)
    def _make_bar(self):
        cv = tk.Canvas(self.tree, highlightthickness=0, bd=0, cursor="arrow")
        cv._keep_bg, cv._sig = True, None
        for ev in ("<Button-1>", "<Double-1>", "<Button-3>", "<ButtonRelease-1>", "<Control-Button-1>"):
            cv.bind(ev, lambda e, ev=ev, cv=cv: self.tree.event_generate(ev, x=cv.winfo_x() + e.x, y=cv.winfo_y() + e.y, rootx=e.x_root, rooty=e.y_root))
        return cv

    def _place_bars(self):
        pool, used, p = self._bar_pool, 0, self.theme.p
        selected = set(self.tree.selection())
        for iid, (frac, tone, odd) in self._bars.items():
            try:
                bb = self.tree.bbox(iid, "status")
            except tk.TclError:
                bb = ""
            if not bb:
                continue
            if used >= len(pool):
                pool.append(self._make_bar())
            cv, used = pool[used], used + 1
            x, y, w, h = bb
            pad, bh = self.px(10), max(3, self.px(4))
            bw = max(self.px(16), w - 2 * pad)
            bg = p["selected"] if iid in selected else p["hover"] if iid == self._hover_row else p["zebra"] if odd else p["surface"]
            sig = (bw, bh, round(frac, 3), tone, bg, p["track"])
            cv.place(x=x + pad, y=y + h - bh - self.px(4), width=bw, height=bh)
            if cv._sig != sig:
                cv._sig = sig
                cv.configure(bg=bg)
                cv.delete("all")
                r, mid = bh / 2.0, bh / 2.0
                cv.create_line(r, mid, bw - r, mid, width=bh, capstyle="round", fill=p["track"] if p["mode"] == "light" or tone != "muted" else p["track"])
                if frac > 0:
                    cv.create_line(r, mid, r + (bw - 2 * r) * frac, mid, width=bh, capstyle="round", fill=p[tone] if tone != "muted" else p["muted"])
        for cv in pool[used:]:
            cv.place_forget()

    def on_double_click(self, e):
        if not self.tree.identify_row(e.y):
            return
        sel = self.selected()
        if sel and sel[0].status == "Completed":
            self.open_file()
        elif sel:
            self.progress_window(sel[0])

    # ------------------------------------------------------------------ enabling / greying out
    def flags(self):
        sel, items = self.selected(), self.mgr.items
        return {"sel": bool(sel), "sel1": len(sel) == 1,
                "done": any(d.status == "Completed" and d.path and os.path.exists(d.path) for d in sel),
                "done1": len(sel) == 1 and sel[0].status == "Completed" and bool(sel[0].path),
                "resumable": any(d.status in ("Paused", "Error", "Queued") for d in sel),
                "active": any(d.status in ACTIVE or d.status == "Queued" for d in sel),
                "anyactive": any(d.status in ACTIVE or d.status == "Queued" for d in items),
                "anydone": any(d.status == "Completed" for d in items)}

    def update_state(self):
        fl = self.flags()
        for icon, rule in (("resume", "resumable"), ("stop", "active"), ("stopall", "anyactive"), ("delete", "sel"), ("delc", "anydone"), ("scan", "done")):
            if icon in self.tbtn:  # the user may have taken the button off the toolbar
                self.tbtn[icon].state(["!disabled"] if fl[rule] else ["disabled"])
        for m, idx, rule in self.menu_rules:
            m.entryconfig(idx, state="normal" if fl[rule] else "disabled")
            icon = self._menu_icons.get((str(m), idx))
            if icon:
                m.entryconfig(idx, image=self.theme.padded_icon(icon, 16) if fl[rule] else self.theme.padded_icon(icon, 16, color=self.theme.p["disabled"]))

    def tick_once(self):
        self.draw_list()
        self.update_side()

    # ------------------------------------------------------------------ context menus + keyboard
    def _fill_cat_menu(self, menu):
        menu.delete(0, "end")
        for c in self.mgr.settings["categories"]:
            menu.add_command(label=c["name"], command=lambda n=c["name"]: self.move_selected_category(n))

    def _fill_queue_menu(self, menu):
        menu.delete(0, "end")
        for q in self.mgr.settings["queues"]:
            menu.add_command(label=q, command=lambda n=q: self.move_selected_queue(n))

    def build_context_menus(self):
        self.ctx = ctx = tk.Menu(self.root, tearoff=0)
        self.ctx_rules = {"Open": "done", "Open folder": "sel", "Resume": "resumable", "Stop": "active", "Delete": "sel", "Move to category": "sel",
                          "Move to queue": "sel", "Limit speed...": "sel", "Redownload": "sel", "Properties...": "sel1", "Copy address": "sel", "Hashes...": "done1"}
        ctx.add_command(label="Open", command=self.open_file)
        ctx.add_command(label="Open folder", command=self.open_folder)
        ctx.add_separator()
        ctx.add_command(label="Resume", command=self.resume)
        ctx.add_command(label="Stop", command=self.stop)
        ctx.add_command(label="Delete", command=self.delete)
        ctx.add_separator()
        cat = tk.Menu(ctx, tearoff=0, postcommand=lambda: self._fill_cat_menu(cat))
        que = tk.Menu(ctx, tearoff=0, postcommand=lambda: self._fill_queue_menu(que))
        ctx.add_cascade(label="Move to category", menu=cat)
        ctx.add_cascade(label="Move to queue", menu=que)
        ctx.add_separator()
        ctx.add_command(label="Limit speed...", command=self.limit_selected)
        ctx.add_command(label="Redownload", command=self.redownload)
        ctx.add_command(label="Hashes...", command=self.hashes_selected)
        ctx.add_command(label="Properties...", command=self.properties_dialog)
        ctx.add_command(label="Copy address", command=self.copy_address)
        for ev in ("<Button-3>", "<Button-2>"):  # Button-2 is the right button on macOS
            self.tree.bind(ev, self.show_ctx)
            self.side.bind(ev, self.show_side_ctx)

    def _popup(self, menu, e):
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def show_ctx(self, e):
        iid = self.tree.identify_row(e.y)
        if not iid:
            return
        if iid not in self.tree.selection():
            self.tree.selection_set(iid)
        fl = self.flags()
        for i in range(self.ctx.index("end") + 1):
            if self.ctx.type(i) != "separator":
                self.ctx.entryconfig(i, state="normal" if fl[self.ctx_rules[self.ctx.entrycget(i, "label")]] else "disabled")
        self._popup(self.ctx, e)

    def show_side_ctx(self, e):
        iid = self.side.identify_row(e.y)
        if iid not in self.side_map:
            return
        self.side.selection_set(iid)
        label, f = self.side_map[iid]
        m = tk.Menu(self.root, tearoff=0)
        if f.startswith("queue:"):
            m.add_command(label="Start queue", command=self.start_queue)
            m.add_command(label="Stop queue", command=self.stop_queue)
            m.add_separator()
            m.add_command(label="Rename...", command=lambda: self.rename_queue_node(label), state="disabled" if label == MAIN_QUEUE else "normal")
            m.add_command(label="Delete queue", command=lambda: self.delete_queue_node(label), state="disabled" if label == MAIN_QUEUE else "normal")
        elif iid == "queues":
            m.add_command(label="New queue...", command=self.new_queue)
        elif f.startswith("project:"):
            m.add_command(label="Forget this project label", command=lambda: self.forget_project(label))
        elif f.startswith("cat:") or iid == "all":
            m.add_command(label="Edit categories...", command=self.categories_dialog)
        else:
            return
        self._popup(m, e)

    def bind_keys(self):
        r, t = self.root, self.tree
        r.bind("<Control-n>", lambda e: self.add_dialog())
        r.bind("<Control-r>", lambda e: self.resume())
        r.bind("<Control-s>", lambda e: self.stop())
        r.bind("<F5>", lambda e: self.tick_once())
        t.bind("<Delete>", lambda e: self.delete())
        t.bind("<F2>", lambda e: self.rename_file())
        t.bind("<Alt-Return>", lambda e: self.properties_dialog())
        t.bind("<Return>", lambda e: self.open_file() if self.flags()["done"] else self.properties_dialog())
        t.bind("<Control-c>", lambda e: self.copy_address())
        t.bind("<Control-a>", lambda e: (t.selection_set(t.get_children()), "break")[1])

    # ------------------------------------------------------------------ download actions
    def after_change(self):
        self.rebuild_side()
        self.draw_list()
        self.update_state()

    def flash(self, text, seconds=6):
        self.note = (text, time.time() + seconds)

    def resume_items(self, ds):
        for d in ds:
            if d.status in ("Paused", "Error", "Queued"):
                d.status, d.force, d.auto_paused = "Queued", True, False  # a manual start ignores the scheduler window

    def pause_items(self, ds):
        for d in ds:
            d.auto_paused = d.force = False
            if d.status in ACTIVE:
                d.pause()
            elif d.status == "Queued":
                d.status = "Paused"

    def resume(self):
        self.resume_items(self.selected())
        self.draw_list()
        self.update_state()

    def stop(self):
        self.pause_items(self.selected())
        self.draw_list()
        self.update_state()

    def stop_all(self):
        self.pause_items(self.mgr.items)
        self.draw_list()
        self.update_state()

    def confirm_delete(self, sel):
        """IDM-style confirmation. Returns (confirmed, also_delete_finished_files_from_disk)."""
        win = tk.Toplevel(self.root)
        win.title("Delete")
        win.transient(self.root)
        win.resizable(False, False)
        out, also = {"ok": False}, tk.BooleanVar(value=False)
        names = ", ".join(d.label[:40] for d in sel[:3]) + (" ..." if len(sel) > 3 else "")
        ttk.Label(win, text=f"Delete {len(sel)} download{'s' if len(sel) > 1 else ''} from the list?\n{names}", justify="left").pack(padx=16, pady=(16, 8))
        if any(d.status == "Completed" for d in sel):
            ttk.Checkbutton(win, text="Also delete the downloaded file(s) from disk", variable=also).pack(anchor="w", padx=16)
        row = ttk.Frame(win)
        row.pack(pady=14)
        ttk.Button(row, text="Yes", style="Accent.TButton", command=lambda: (out.update(ok=True), win.destroy())).pack(side="left", padx=6)
        ttk.Button(row, text="No", command=win.destroy).pack(side="left", padx=6)
        win.grab_set()
        win.wait_window()
        return out["ok"], also.get()

    def delete(self):
        sel = self.selected()
        if not sel:
            return
        ok, files = self.confirm_delete(sel)
        if ok:
            for d in sel:
                self.mgr.remove(d, delete_file=True, delete_completed=files)
            self.after_change()

    def delete_completed(self):
        done = [d for d in self.mgr.items if d.status == "Completed"]
        if not done:
            return self.info("Delete completed", "There are no completed downloads in the list.")
        if messagebox.askyesno("Delete completed", f"Remove {len(done)} completed download(s) from the list?\n(The files stay on disk.)", parent=self.root):
            for d in done:
                self.mgr.remove(d)
            self.after_change()

    def start_queue(self):
        q = self.cur_queue()
        self.flash(f"Queue '{q}': {self.mgr.start_queue(q)} download(s) queued to start")
        self.draw_list()
        self.update_state()

    def stop_queue(self):
        q = self.cur_queue()
        self.flash(f"Queue '{q}': {self.mgr.stop_queue(q)} download(s) stopped")
        self.draw_list()
        self.update_state()

    def new_queue(self):
        name = simpledialog.askstring("New queue", "Name of the new queue:", parent=self.root)
        if name is not None:
            try:
                self.mgr.add_queue(name)
            except ValueError as e:
                return messagebox.showerror("New queue", str(e), parent=self.root)
            self.after_change()

    def rename_queue_node(self, old):
        new = simpledialog.askstring("Rename queue", "New name:", initialvalue=old, parent=self.root)
        if new is not None and new != old:
            try:
                self.flt.set("queue:" + self.mgr.rename_queue(old, new))
            except ValueError as e:
                return messagebox.showerror("Rename queue", str(e), parent=self.root)
            self.after_change()

    def delete_queue_node(self, name):
        if messagebox.askyesno("Delete queue", f"Delete the queue '{name}'?\nIts downloads move to '{MAIN_QUEUE}'.", parent=self.root):
            self.mgr.delete_queue(name)
            self.flt.set("queues")
            self.after_change()

    def forget_project(self, name):
        for d in self.mgr.items:
            if d.project == name:
                d.project = ""
        self.flt.set("projects")
        self.after_change()

    def move_selected_category(self, cat):
        for d in self.selected():
            try:
                self.mgr.move_to_category(d, cat)
            except ValueError as e:
                self.info("Move to category", f"{d.label}\n\n{e}")
                break
        self.after_change()

    def move_selected_queue(self, name):
        for d in self.selected():
            self.mgr.move_to_queue(d, name)
        self.after_change()

    # ------------------------------------------------------------------ file actions
    def open_path(self, target):
        try:
            if platform.system() == "Windows":
                os.startfile(target)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        except OSError as e:
            messagebox.showerror("AeroGrab", f"Couldn't open {target}\n{e}", parent=self.root)

    def open_file(self):
        sel = self.selected()
        if sel and sel[0].status == "Completed" and sel[0].path and os.path.exists(sel[0].path):
            self.open_path(sel[0].path)

    def open_folder(self):
        sel = self.selected()
        target = (os.path.dirname(sel[0].path) if sel and sel[0].path else sel[0].folder if sel else self.folder.get())
        self.open_path(target if os.path.isdir(target) else self.folder.get())

    def rename_file(self):
        sel = self.selected()
        if len(sel) != 1 or sel[0].status != "Completed" or not sel[0].path or not os.path.exists(sel[0].path):
            return
        d = sel[0]
        new = simpledialog.askstring("Move/Rename", "New file name:", initialvalue=os.path.basename(d.path), parent=self.root)
        if not new or new == os.path.basename(d.path):
            return
        target = os.path.join(os.path.dirname(d.path), clean_name(new))
        if os.path.exists(target):
            return messagebox.showerror("Move/Rename", "A file with that name already exists.", parent=self.root)
        try:
            os.rename(d.path, target)
        except OSError as e:
            return messagebox.showerror("Move/Rename", str(e), parent=self.root)
        d.path, d.name = target, os.path.basename(target)
        self.draw_list()

    def redownload(self):
        sel = self.selected()
        if not sel or not messagebox.askyesno("Redownload", f"Download {len(sel)} item(s) again?\nA finished file is kept; the new copy gets a number.", parent=self.root):
            return
        for d in sel:
            kw = dict(referer=d.referer, cookie=d.cookie, ua=d.ua, hint=d.hint, queue=d.queue, project=d.project, desc=d.desc)
            kind = "hls" if isinstance(d, HlsDownload) else "mux" if isinstance(d, MuxDownload) else "dash" if isinstance(d, DashDownload) else "ytdlp" if isinstance(d, ExtractDownload) else None
            if kind in ("dash", "ytdlp"):
                kw.update(quality=d.quality)
            if kind == "hls":
                kw.update(quality=d.quality, pick_bw=d.pick_bw)
            elif kind == "mux":
                kw["audio_url"] = d.audio_url
            self.mgr.add(d.url, d.base, d.connections, kind=kind, **kw)
        self.after_change()

    def limit_selected(self):
        sel = self.selected()
        if not sel:
            return
        kb = simpledialog.askinteger("Speed limit", "Limit for the selected download(s) in KBytes/sec (0 = no limit):",
                                     parent=self.root, minvalue=0, initialvalue=sel[0].limit_kb)
        if kb is not None:
            for d in sel:
                d.set_limit(kb)

    def copy_address(self):
        sel = self.selected()
        if sel:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(d.url for d in sel))

    def hashes_selected(self):
        sel = self.selected()
        if len(sel) == 1:
            self.hashes_dialog(sel[0])

    def hashes_dialog(self, d):
        """MD5 / SHA-1 / SHA-256 / SHA-512 of a finished file, worked out in the background, with a box to compare a published value against."""
        if not d.path or not os.path.isfile(d.path):
            return self.info("File hashes", "The file isn't on disk (yet).")
        win = tk.Toplevel(self.root)
        win.title("File hashes")
        win.transient(self.root)
        ttk.Label(win, text=os.path.basename(d.path), font="AeroBold").grid(row=0, column=0, columnspan=3, sticky="w", padx=14, pady=(12, 6))
        vals = {a: tk.StringVar(value="calculating...") for a in HASH_ALGOS}
        for r, a in enumerate(HASH_ALGOS, 1):
            ttk.Label(win, text={"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256", "sha512": "SHA-512"}[a] + ":").grid(row=r, column=0, sticky="e", padx=(14, 6), pady=3)
            e = ttk.Entry(win, textvariable=vals[a], width=72)
            e.state(["readonly"])
            e.grid(row=r, column=1, pady=3)
            ttk.Button(win, text="Copy", command=lambda a=a: (self.root.clipboard_clear(), self.root.clipboard_append(vals[a].get()))).grid(row=r, column=2, padx=(6, 14))
        ttk.Label(win, text="Compare with:").grid(row=5, column=0, sticky="e", padx=(14, 6), pady=(10, 3))
        want = tk.StringVar()
        ttk.Entry(win, textvariable=want, width=72).grid(row=5, column=1, pady=(10, 3))
        verdict = ttk.Label(win, text="")
        verdict.grid(row=6, column=1, sticky="w")
        stop, res = threading.Event(), {}
        threading.Thread(target=lambda: res.update(h=hash_file_multi(d.path, stop=stop)), daemon=True).start()

        def judge(*_):
            t = want.get().strip()
            cs = parse_checksum(t)
            if not t:
                return verdict.config(text="")
            if not cs:
                return verdict.config(text="That isn't an MD5, SHA-1, SHA-256 or SHA-512 value.", style="Danger.TLabel")
            if not res.get("h"):
                return verdict.config(text="Still calculating...", style="Muted.TLabel")
            same = res["h"].get(cs[0]) == cs[1]
            verdict.config(text="MATCH - the file is intact." if same else "DOES NOT MATCH - the file differs from that value.", style="Success.TLabel" if same else "Danger.TLabel")
        want.trace_add("write", judge)

        def poll():
            if not win.winfo_exists():
                return
            if "h" in res:
                for a in HASH_ALGOS:
                    vals[a].set(res["h"].get(a, ""))
                judge()
            else:
                win.after(150, poll)
        poll()
        win.bind("<Destroy>", lambda e: stop.set() if e.widget is win else None)
        ttk.Button(win, text="Close", command=win.destroy).grid(row=7, column=0, columnspan=3, pady=12)

    def properties_dialog(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        d = sel[0]
        win = tk.Toplevel(self.root)
        win.title("Download properties")
        win.transient(self.root)
        rows = (("File name", d.name or "(not known yet)"), ("Save to", os.path.dirname(d.path) if d.path else d.folder), ("Address", d.url),
                ("Referer", d.referer or ""), ("Category", d.category), ("Queue", d.queue), ("Status", status_text(d)),
                ("Size", human(d.size) if d.size > 0 else "unknown"), ("Downloaded", human(d.done)), ("Last try", fmt_when(d.last_try)))
        for r, (k, v) in enumerate(rows):
            ttk.Label(win, text=k + ":").grid(row=r, column=0, sticky="e", padx=(14, 6), pady=3)
            e = ttk.Entry(win, width=70)
            e.insert(0, v)
            e.state(["readonly"])
            e.grid(row=r, column=1, padx=(0, 14), pady=3)
        ttk.Label(win, text="Description:").grid(row=len(rows), column=0, sticky="e", padx=(14, 6), pady=3)
        desc = tk.StringVar(value=d.desc)
        ttk.Label(win, text="Expected hash:").grid(row=len(rows) + 1, column=0, sticky="e", padx=(14, 6), pady=3)
        hv = tk.StringVar(value=d.checksum)
        hrow = ttk.Frame(win)
        hrow.grid(row=len(rows) + 1, column=1, sticky="w", pady=3)
        ttk.Entry(hrow, textvariable=hv, width=58).pack(side="left")
        ttk.Button(hrow, text="Hashes...", command=lambda: self.hashes_dialog(d)).pack(side="left", padx=(6, 0))
        verdict = {"ok": "matched", "bad": "DID NOT MATCH", "missing": "could not be checked (file missing)"}.get(d.verified, "")
        ttk.Label(win, style="Muted.TLabel", text="MD5, SHA-1, SHA-256 or SHA-512. Checked automatically when the download finishes"
                  + (f" - the last check {verdict}." if verdict else ".")).grid(row=len(rows) + 2, column=1, sticky="w")
        ttk.Entry(win, textvariable=desc, width=70).grid(row=len(rows), column=1, padx=(0, 14), pady=3)  # created last: it is the dialog's last text box

        def ok():
            try:
                cs = normalize_checksum(hv.get())
            except ValueError:
                return messagebox.showerror("Checksum", "That isn't an MD5, SHA-1, SHA-256 or SHA-512 value.", parent=win)
            d.desc = desc.get().strip()
            d.set_checksum(cs)
            win.destroy()
            self.draw_list()
        row = ttk.Frame(win)
        row.grid(row=len(rows) + 3, column=0, columnspan=2, pady=12)
        ttk.Button(row, text="OK", style="Accent.TButton", command=ok).pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    # ------------------------------------------------------------------ IDM-style windows: confirm, progress, complete
    def _guard(self, fn, *a):
        """Run one step of the refresh loop; a bug in a dialog must never stop the whole GUI from updating."""
        try:
            fn(*a)
        except Exception:
            import traceback
            traceback.print_exc()

    def _front(self, win):
        """Bring a dialog to the front even when the main window is hidden in the tray."""
        try:
            win.deiconify()
            win.lift()
            win.attributes("-topmost", True)
            win.after(400, lambda: win.winfo_exists() and win.attributes("-topmost", False))
            win.focus_force()
        except tk.TclError:
            pass

    def _capture(self, job):
        """Called from the API thread for every link the browser sends."""
        now = time.time()
        seen = self.__dict__.setdefault("recent_captures", {})   # url -> time it was last offered
        for u in [u for u, t in seen.items() if now - t > CAPTURE_DEDUPE_SECS]:
            seen.pop(u, None)
        if job["url"] in seen or job["url"] in self.pending_urls:  # the browser sometimes sends a link twice
            return
        seen[job["url"]] = now
        if self.mgr.settings.get("dup_links", "ask") == "skip" and self.mgr.find_duplicate(job["url"]):
            return  # Configuration > Downloads: links already in the list are ignored
        if self.mgr.settings.get("confirm_captured", True):
            if self.captured.qsize() >= CAPTURE_MAX_QUEUE:  # a page spraying links: don't bury the user in windows
                return
            job["_t"] = now
            self.captured.put(job)  # the GUI thread shows the confirmation window
        else:
            self.mgr.add(job["url"], job["folder"], job["connections"], kind=job["kind"], **job["kw"])

    def _capture_pump(self):
        """Look for a captured link every CAPTURE_PUMP_MS (the main tick only runs every 500 ms), so the dialog shows up almost at once."""
        self._guard(self.drain_captured)
        self.root.after(CAPTURE_PUMP_MS, self._capture_pump)

    def drain_captured(self):
        # One confirmation window at a time; the rest wait in the queue (and expire if the user never gets to them).
        while not self.pending_urls:
            try:
                job = self.captured.get_nowait()
            except queue.Empty:
                return
            if time.time() - job.get("_t", time.time()) > CAPTURE_EXPIRE_SECS:
                continue
            if not self.dup_ok(job["url"]):
                continue
            self.confirm_dialog(job)

    def dup_ok(self, url):
        """Configuration > Downloads > duplicate links: ask / skip / add anyway. True = go ahead and add."""
        mode = self.mgr.settings.get("dup_links", "ask")
        dup = None if mode == "add" else self.mgr.find_duplicate(url)
        if dup is None:
            return True
        if mode == "skip":
            self.flash(f"Already in the list: {dup.label}")
            return False
        return bool(messagebox.askyesno("Duplicate link", f"This link is already in the list:\n{dup.label} ({dup.status})\n\nAdd it again?", parent=self.root))

    def poll_clipboard(self):
        """Configuration > General > 'Automatically start downloading URLs placed to clipboard' (still asks first if the confirm option is on)."""
        st = self.mgr.settings
        if not st.get("clip_monitor"):
            self._autoclip_last = None
            return
        now = time.time()
        if now - getattr(self, "_autoclip_t", 0) < 1:
            return
        self._autoclip_t = now
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            return
        first = getattr(self, "_autoclip_last", None) is None  # the first look only remembers what is already there
        if text == getattr(self, "_autoclip_last", None):
            return
        self._autoclip_last = text
        if first or "\n" in text or not text.lower().startswith(("http://", "https://")):
            return
        if url_ext(text) in split_list(st.get("capture_types")) and capture_decision(st, text):
            self._capture({"url": text, "folder": self.folder.get(), "connections": self.conns.get(), "kind": None, "kw": {}})

    def confirm_dialog(self, job):
        """'Download File Info': a captured link only starts when the user clicks Start Download."""
        url, kw = job["url"], job["kw"]
        kind = job["kind"] or detect_kind(url)
        self.pending_urls.add(url)
        win = tk.Toplevel(self.root)
        win.title("Download File Info")
        win.resizable(False, False)
        folder, cat, que = tk.StringVar(value=job["folder"]), tk.StringVar(value="Automatic"), tk.StringVar(value=MAIN_QUEUE)
        guess = kw.get("hint") or urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
        if kind in ("hls", "mux") and guess and not os.path.splitext(guess)[1]:
            guess += ".mp4"
        if kind == "ytdlp" and not kw.get("hint"):
            guess = ""
        name = tk.StringVar(value=clean_name(guess) if guess else "(taken from the video page)" if kind == "ytdlp" else "(not known yet)")
        known = capture_summary(job.get("meta"), kind)  # v1.8: quality / format / length / size the browser already knows - shown at once
        size = tk.StringVar(value=known or {"hls": "Video stream (HLS)", "mux": "Video + audio (merged when done)", "dash": "Video stream (DASH, merged by ffmpeg)",
                                            "ytdlp": "Video page - best available quality, found by yt-dlp"}.get(kind, "Checking..."))
        body = ttk.Frame(win, padding=14)
        body.pack(fill="both", expand=True)
        for r, (label, var) in enumerate((("Address", None), ("File name", name), ("File size", size))):
            ttk.Label(body, text=label + ":").grid(row=r, column=0, sticky="e", padx=(0, 8), pady=3)
            if label == "File size":
                ttk.Label(body, textvariable=var).grid(row=r, column=1, columnspan=3, sticky="w", pady=3)
                continue
            e = ttk.Entry(body, width=70, textvariable=var)
            if var is None:
                e.insert(0, url)
            e.state(["readonly"])
            e.grid(row=r, column=1, columnspan=3, sticky="we", pady=3)
        ttk.Label(body, text="Category:").grid(row=3, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Combobox(body, textvariable=cat, state="readonly", width=18, values=["Automatic"] + [c["name"] for c in self.mgr.settings["categories"]]).grid(row=3, column=1, sticky="w", pady=3)
        ttk.Label(body, text="Queue:").grid(row=3, column=2, sticky="e", padx=(12, 8))
        ttk.Combobox(body, textvariable=que, state="readonly", width=24, values=self.mgr.settings["queues"]).grid(row=3, column=3, sticky="w")
        ttk.Label(body, text="Save to:").grid(row=4, column=0, sticky="e", padx=(0, 8), pady=3)
        ttk.Entry(body, textvariable=folder, width=56).grid(row=4, column=1, columnspan=2, sticky="we", pady=3)
        ttk.Button(body, text="Browse...", command=lambda: folder.set(filedialog.askdirectory(parent=win, initialdir=folder.get()) or folder.get())).grid(row=4, column=3, sticky="w", padx=6)
        ttk.Label(body, text="Nothing is downloaded until you click Start Download.", style="Muted.TLabel").grid(row=5, column=1, columnspan=3, sticky="w", pady=(6, 0))

        def close():
            self.pending_urls.discard(url)
            if win.winfo_exists():
                win.destroy()

        def go(later):
            dest = folder.get().strip() or self.folder.get()
            d = self.mgr.add(url, dest, job["connections"], kind=kind, queue=que.get(), later=later, **kw)
            if cat.get() != "Automatic":
                try:
                    self.mgr.move_to_category(d, cat.get())
                except ValueError as e:
                    messagebox.showerror("AeroGrab", str(e), parent=win)
            close()
            if not later:
                self.mgr.kick()  # begin transferring now, not at the next 500 ms tick
            self.after_change()
            if not later:
                self.progress_window(d)

        row = ttk.Frame(win)
        row.pack(pady=(0, 12))
        ttk.Button(row, text="Start Download", style="Accent.TButton", command=lambda: go(False)).pack(side="left", padx=6)
        ttk.Button(row, text="Download Later", command=lambda: go(True)).pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=close).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", close)
        self._front(win)

        if kind is None:  # like IDM, ask the server for the real name and size (a 1-byte request; no file data is downloaded)
            box = {}

            def probe():
                try:
                    t = Download(url, folder.get(), 1, referer=kw.get("referer"), cookie=kw.get("cookie"), ua=kw.get("ua"), hint=kw.get("hint"))
                    t._probe()
                    box["r"] = (t.name, t.size)
                except Exception:
                    box["r"] = (None, -1)
            threading.Thread(target=probe, daemon=True).start()

            def poll():
                if not win.winfo_exists():
                    return
                if "r" not in box:
                    return win.after(60, poll)
                n, z = box["r"]
                if n:
                    name.set(n)
                size.set(f"{human(z)} ({z:,} Bytes)" if z and z > 0 else known or "unknown")
            poll()

    def progress_window(self, d):
        """The live window of a running download: Download status / Speed Limiter / Options on completion."""
        old = self.pwins.get(id(d))
        if old and old["win"].winfo_exists():
            return self._front(old["win"])
        st = self.mgr.settings
        win = tk.Toplevel(self.root)
        win.minsize(540, 120)
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        # ---- tab 1: Download status
        t1 = ttk.Frame(nb, padding=10)
        nb.add(t1, text="Download status")
        url_e = ttk.Entry(t1)
        url_e.insert(0, d.url)
        url_e.state(["readonly"])
        url_e.pack(fill="x", pady=(0, 6))
        grid = ttk.Frame(t1)
        grid.pack(fill="x")
        lab = {}
        for r, k in enumerate(("Status", "File size", "Downloaded", "Transfer rate", "Time left", "Resume capability")):
            ttk.Label(grid, text=k, width=18).grid(row=r, column=0, sticky="w", pady=1)
            lab[k] = ttk.Label(grid, text="")
            lab[k].grid(row=r, column=1, sticky="w", pady=1)
        bar = ttk.Progressbar(t1, maximum=100)
        bar.pack(fill="x", pady=(8, 4))
        cv = tk.Canvas(t1, height=14, highlightthickness=0, background=PAL["map_bg"])
        cv.pack(fill="x", pady=(0, 6))
        details = ttk.Frame(t1)
        details.pack(fill="both", expand=True)
        tv = ttk.Treeview(details, columns=("n", "got", "info"), show="headings", height=8, selectmode="none")
        for c, text, w, anchor in (("n", "N.", 50, "center"), ("got", "Downloaded", 130, "e"), ("info", "Info", 260, "w")):
            tv.heading(c, text=text)
            tv.column(c, width=w, anchor=anchor)
        sb = ttk.Scrollbar(details, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # ---- tab 2: Speed Limiter
        t2 = ttk.Frame(nb, padding=14)
        nb.add(t2, text="Speed Limiter")
        use, kb = tk.BooleanVar(value=d.limit_kb > 0), tk.IntVar(value=d.limit_kb or 100)
        spin = ttk.Spinbox(t2, from_=1, to=10_000_000, width=9, textvariable=kb)
        lim_note = ttk.Label(t2, style="Muted.TLabel")

        def apply_limit(*_):
            try:
                v = max(1, int(kb.get()))
            except (tk.TclError, ValueError):
                v = d.limit_kb or 100
            kb.set(v)
            d.set_limit(v if use.get() else 0)
            spin.state(["!disabled"] if use.get() else ["disabled"])
            lim_note.config(text=f"This download is limited to {v} KBytes/sec." if use.get() else "No limit for this download (the global limit still applies).")
        ttk.Checkbutton(t2, text="Use speed limiter", variable=use, command=apply_limit).pack(anchor="w")
        r2 = ttk.Frame(t2)
        r2.pack(anchor="w", pady=8)
        ttk.Label(r2, text="Maximum download speed (KBytes/sec):").pack(side="left")
        spin.pack(side="left", padx=8)
        ttk.Button(r2, text="Apply", command=apply_limit).pack(side="left")
        lim_note.pack(anchor="w")
        apply_limit()

        # ---- tab 3: Options on completion
        t3 = ttk.Frame(nb, padding=14)
        nb.add(t3, text="Options on completion")
        show = tk.BooleanVar(value=st.get("show_complete_dialog", True) if d.show_complete is None else d.show_complete)
        opn, ext, off = tk.BooleanVar(value=d.open_when_done), tk.BooleanVar(value=st.get("after") == "exit"), tk.BooleanVar(value=st.get("after") == "shutdown")

        def sync(which=""):
            d.show_complete, d.open_when_done = show.get(), opn.get()
            if which == "exit" and ext.get():
                off.set(False)
            if which == "off" and off.get():
                ext.set(False)
            st["after"] = "exit" if ext.get() else "shutdown" if off.get() else "none"
            self.mgr.save_settings()
        for text, var, which in (("Show download complete dialog", show, ""), ("Open the file when done", opn, ""),
                                 ("Exit AeroGrab when all downloads are done", ext, "exit"), ("Turn off computer when all downloads are done", off, "off")):
            ttk.Checkbutton(t3, text=text, variable=var, command=lambda w=which: sync(w)).pack(anchor="w", pady=3)

        # ---- buttons
        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=8, pady=8)
        hide_txt = tk.StringVar(value="<< Hide details")
        pause_txt = tk.StringVar(value="Pause")

        def toggle_details():
            if details.winfo_ismapped():
                details.pack_forget()
                hide_txt.set("Show details >>")
            else:
                details.pack(fill="both", expand=True)
                hide_txt.set("<< Hide details")

        def pause_resume():
            (self.pause_items if d.status in ACTIVE or d.status == "Queued" else self.resume_items)([d])
            self.draw_list()
            self.update_state()

        def close():
            self.pwins.pop(id(d), None)
            if win.winfo_exists():
                win.destroy()

        def cancel():
            self.pause_items([d])
            self.draw_list()
            close()
        ttk.Button(btns, textvariable=hide_txt, command=toggle_details).pack(side="left")
        ttk.Button(btns, text="Cancel", command=cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, textvariable=pause_txt, command=pause_resume).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", close)

        cache = {"rows": None}

        def refresh():
            if d not in self.mgr.items or d.status == "Completed":
                return close()  # a finished download is announced by the Download complete dialog
            pct = d.percent
            win.title(f"{pct:.0f}% - {d.label[:40]}" if d.status in ACTIVE else d.label[:50])
            lab["Status"].config(text=status_text(d))
            lab["File size"].config(text=f"{human(d.size)} ({d.size:,} Bytes)" if d.size > 0 else "unknown")
            lab["Downloaded"].config(text=f"{human(d.done)} ({pct:.2f}%)" if d.size > 0 or pct else human(d.done))
            lab["Transfer rate"].config(text=fmt_rate(d.speed) or "-")
            lab["Time left"].config(text=fmt_left(d.eta_sec) or "-")
            lab["Resume capability"].config(text="Yes" if d.ranges or isinstance(d, (HlsDownload, MuxDownload)) else "No" if d.name else "Unknown")
            bar["value"] = pct
            pause_txt.set("Pause" if d.status in ACTIVE or d.status == "Queued" else "Resume")
            cv.delete("all")
            W, H = max(cv.winfo_width(), 100), max(cv.winfo_height(), 10)
            for x0, x1, xf in d.segment_map():
                cv.create_rectangle(x0 * W, 1, x1 * W, H - 1, fill=PAL["seg_empty"], outline=PAL["seg_border"])
                if xf > x0:
                    cv.create_rectangle(x0 * W, 1, xf * W, H - 1, fill=PAL["accent"], outline="")
            rows = d.segment_rows()
            if rows != cache["rows"]:
                cache["rows"] = rows
                have = tv.get_children()
                for i, vals in enumerate(rows):
                    if i < len(have):
                        tv.item(have[i], values=vals)
                    else:
                        tv.insert("", "end", values=vals)
                for iid in have[len(rows):]:
                    tv.delete(iid)
        self.pwins[id(d)] = {"win": win, "d": d, "refresh": refresh}
        refresh()
        self._front(win)

    def update_progress_windows(self):
        for key, w in list(self.pwins.items()):
            if w["win"].winfo_exists():
                w["refresh"]()
            else:
                self.pwins.pop(key, None)

    def check_completed(self):
        """Pops up the Download complete dialog once for each download that finishes."""
        for d in list(self.mgr.items):
            if d.status != "Completed" or d.announced:
                continue
            if d.checksum and not d.verified:
                continue  # the hash check is still running: announce the download with its verdict
            if d._scanning and time.time() - d._scan_t0 < 8:
                continue  # a quick virus scan gets a moment, so the dialog can show its verdict (a slow one updates the open dialog)
            d.announced, d._scan_shown = True, bool(d.scan)
            if d.verified == "bad" and self.tray and self.mgr.settings.get("notify", True):
                self.tray.notify(f"Checksum does NOT match: {d.label}")
            w = self.pwins.pop(id(d), None)
            if w and w["win"].winfo_exists():
                w["win"].destroy()
            if d.open_when_done and d.path and os.path.exists(d.path) and d.scan != "infected":  # never auto-open a file the antivirus flagged
                self.open_path(d.path)
            show = self.mgr.settings.get("show_complete_dialog", True) if d.show_complete is None else d.show_complete
            if show:
                self.complete_dialog(d)

    def open_with(self, path, parent):
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", path])
                return
            prog = filedialog.askopenfilename(parent=parent, title="Open with...", initialdir="/Applications" if system == "Darwin" else "/usr/bin")
            if prog:
                subprocess.Popen(["open", "-a", prog, path] if system == "Darwin" else [prog, path])
        except OSError as e:
            messagebox.showerror("AeroGrab", f"Couldn't open the file with that program.\n{e}", parent=parent)

    def reveal(self, path):
        """Open the file's folder, with the file highlighted where the OS supports it."""
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", "/select," + os.path.normpath(path)])
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                self.open_path(os.path.dirname(path))
        except OSError as e:
            messagebox.showerror("AeroGrab", f"Couldn't open the folder.\n{e}", parent=self.root)

    def complete_dialog(self, d):
        """IDM's 'Download complete' window."""
        path = os.path.normpath(d.path) if d.path else ""
        try:
            nbytes = os.path.getsize(path)
        except OSError:
            nbytes = d.size
        win = tk.Toplevel(self.root)
        win.title("Download complete")
        win.resizable(False, False)
        top = ttk.Frame(win, padding=(14, 12, 14, 4))
        top.pack(fill="x")
        try:
            win._icon = tk.PhotoImage(data=ICON_B64).subsample(3)
            ttk.Label(top, image=win._icon).pack(side="left", padx=(0, 12))
        except tk.TclError:
            pass
        head = ttk.Frame(top)
        head.pack(side="left", fill="x")
        ttk.Label(head, text="Download complete", font="AeroHeading").pack(anchor="w")
        ttk.Label(head, text=f"{size_mb_bytes(nbytes)} downloaded").pack(anchor="w", pady=(2, 0))
        body = ttk.Frame(win, padding=(14, 6))
        body.pack(fill="x")
        for r, (k, v) in enumerate((("Address", d.url), ("Saved to", path))):
            ttk.Label(body, text=k + ":").grid(row=r, column=0, sticky="e", padx=(0, 8), pady=3)
            e = ttk.Entry(body, width=64)
            e.insert(0, v)
            e.state(["readonly"])
            e.grid(row=r, column=1, sticky="we", pady=3)
        if d.verified in ("ok", "bad", "missing"):
            algo = d.checksum.split(":")[0].upper()
            msg, col = {"ok": (f"{algo} checksum verified - the file is intact.", "Success.TLabel"),
                        "bad": (f"WARNING: the {algo} checksum does NOT match.\nExpected  {d.checksum.split(':')[1]}\nThe file   {d.actual_hash}\n"
                                "The file may be damaged or have been tampered with.", "Danger.TLabel"),
                        "missing": ("The checksum couldn't be checked: the file is gone.", "Danger.TLabel")}[d.verified]
            ttk.Label(win, text=msg, style=col, wraplength=560, justify="left").pack(anchor="w", padx=14, pady=(2, 0))
        scan_lbl = ttk.Label(win, text="", wraplength=560, justify="left")
        scan_lbl.pack(anchor="w", padx=14, pady=(2, 0))

        def show_scan():  # the antivirus verdict; it keeps updating while a slow scan is still running
            try:
                if not win.winfo_exists():
                    return
                if d._scanning:
                    scan_lbl.config(text="Scanning for viruses...", style="Muted.TLabel")
                    win.after(500, show_scan)
                    return
                if d.scan_info:
                    scan_lbl.config(text=d.scan_info + ("\nDon't open this file unless you are sure it is safe." if d.scan == "infected" else ""),
                                    style={"clean": "Success.TLabel", "infected": "Danger.TLabel", "error": "Warning.TLabel"}.get(d.scan, PAL["muted"]))
                else:
                    scan_lbl.pack_forget()
            except tk.TclError:
                pass
        show_scan()
        never = tk.BooleanVar(value=False)

        def finish():
            if never.get():
                self.mgr.settings["show_complete_dialog"] = False
                self.mgr.save_settings()
            if win.winfo_exists():
                win.destroy()

        def need_file():
            if path and os.path.exists(path):
                return True
            messagebox.showerror("AeroGrab", "The file is no longer there.", parent=win)
            return False

        def open_it():
            if not need_file():
                return
            if d.scan == "infected" and not messagebox.askyesno("AeroGrab", f"The antivirus reported:\n{d.scan_info}\n\nOpen the file anyway?", icon="warning", default="no", parent=win):
                return
            self.open_path(path)
            finish()
        row = ttk.Frame(win)
        row.pack(pady=(8, 4))
        for text, fn in (("Open", open_it),
                         ("Open with...", lambda: need_file() and (self.open_with(path, win), finish())),
                         ("Open folder", lambda: need_file() and (self.reveal(path), finish())),
                         ("Close", finish)):
            ttk.Button(row, text=text, command=fn).pack(side="left", padx=5)
        ttk.Checkbutton(win, text="Don't show this dialog again", variable=never).pack(anchor="w", padx=14, pady=(4, 12))
        win.protocol("WM_DELETE_WINDOW", finish)
        self._front(win)

    # ------------------------------------------------------------------ adding downloads
    def add_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Enter new address to download")
        win.transient(self.root)
        ttk.Label(win, text="Address (one link per line):").pack(anchor="w", padx=14, pady=(14, 2))
        txt = tk.Text(win, width=78, height=6)
        txt.pack(padx=14)
        try:
            clip = self.root.clipboard_get().strip()
            if clip.lower().startswith(URL_SCHEMES):
                txt.insert("1.0", clip)
        except tk.TclError:
            pass
        row = ttk.Frame(win)
        row.pack(fill="x", padx=14, pady=10)
        cat, que = tk.StringVar(value="Automatic"), tk.StringVar(value=self.cur_queue())
        ttk.Label(row, text="Category:").pack(side="left")
        ttk.Combobox(row, textvariable=cat, state="readonly", width=16, values=["Automatic"] + [c["name"] for c in self.mgr.settings["categories"]]).pack(side="left", padx=(4, 16))
        ttk.Label(row, text="Queue:").pack(side="left")
        ttk.Combobox(row, textvariable=que, state="readonly", width=22, values=self.mgr.settings["queues"]).pack(side="left", padx=4)
        ttk.Label(win, text="Save to: " + self.folder.get(), style="Muted.TLabel").pack(anchor="w", padx=14)
        hv = tk.StringVar()
        hr = ttk.Frame(win)
        hr.pack(fill="x", padx=14, pady=(8, 0))
        ttk.Label(hr, text="Checksum (optional, for a single address):").pack(side="left")
        ttk.Entry(hr, textvariable=hv, width=46).pack(side="left", padx=6)

        def go(later):
            urls = [x.strip() for x in txt.get("1.0", "end").splitlines() if x.strip().lower().startswith(URL_SCHEMES)]
            if not urls:
                return self.info("Add URL", "Paste at least one http://, https:// or ftp:// address.", win)
            if self.mgr.settings.get("smart_unwrap", True):
                urls = [unwrap_url(u)[0] for u in urls]  # google.com/url?q=..., facebook l.php?u=... : the real address, no network needed
            try:
                cs = normalize_checksum(hv.get())
            except ValueError:
                return self.info("Add URL", "That checksum isn't an MD5, SHA-1, SHA-256 or SHA-512 value.", win)
            if cs and len(urls) != 1:
                return self.info("Add URL", "A checksum belongs to one file: enter a single address.", win)
            added = []
            for u in urls:
                d = self.mgr.add(u, self.folder.get(), self.conns.get(), queue=que.get(), later=later, **({"checksum": cs} if cs else {}))
                if cat.get() != "Automatic":
                    self.mgr.move_to_category(d, cat.get())
                added.append(d)
            win.destroy()
            self.after_change()
            if not later:
                for d in added[:3]:  # a window per download, but not a screenful for a big batch
                    self.progress_window(d)
        note = ttk.Label(win, text="", wraplength=620, justify="left", style="Muted.TLabel")
        note.pack(anchor="w", padx=14, pady=(6, 0))
        btns = ttk.Frame(win)
        btns.pack(pady=(10, 14))
        ttk.Button(btns, text="Start Download", style="Accent.TButton", command=lambda: go(False)).pack(side="left", padx=6)
        ttk.Button(btns, text="Download Later", command=lambda: go(True)).pack(side="left", padx=6)
        ttk.Button(btns, text="Resolve link...", command=lambda: self.resolve_in_dialog(win, txt, note)).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="left", padx=6)
        txt.focus_set()

    def add_from_clipboard(self):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            text = ""
        urls = list(dict.fromkeys(re.findall(r"(?:https?|ftps?)://[^\s<>\"']+", text)))
        if not urls:
            return self.info("Batch download", "The clipboard doesn't contain any http://, https:// or ftp:// links.")
        if messagebox.askyesno("Batch download", f"Download {len(urls)} link(s) from the clipboard?", parent=self.root):
            for u in urls:
                self.mgr.add(u, self.folder.get(), self.conns.get(), queue=self.cur_queue())
            self.after_change()

    def grabber_dialog(self):
        """Site grabber: scan a page (and optionally the pages it links to) for downloadable files."""
        win = tk.Toplevel(self.root)
        win.title("Site Grabber")
        win.transient(self.root)
        top = ttk.Frame(win)
        top.pack(fill="x", padx=12, pady=(12, 4))
        start = tk.StringVar()
        try:
            clip = self.root.clipboard_get().strip()
            if clip.lower().startswith(("http://", "https://")) and "\n" not in clip:
                start.set(clip)
        except tk.TclError:
            pass
        ttk.Label(top, text="Start page:").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=start, width=70).grid(row=0, column=1, columnspan=3, sticky="ew", padx=6)
        ttk.Label(top, text="Look in:").grid(row=1, column=0, sticky="w", pady=6)
        depth = tk.StringVar(value="This page only")
        ttk.Combobox(top, textvariable=depth, state="readonly", width=44,
                     values=["This page only", "This page and the pages it links to on the same site (up to 20)"]).grid(row=1, column=1, sticky="w", padx=6)
        kinds = ttk.LabelFrame(win, text="Find these files")
        kinds.pack(fill="x", padx=12, pady=4)
        checks = {}
        for c in self.mgr.settings["categories"]:
            if c["exts"]:
                checks[c["name"]] = tk.BooleanVar(value=True)
                ttk.Checkbutton(kinds, text=c["name"], variable=checks[c["name"]]).pack(side="left", padx=8, pady=4)
        anyfile = tk.BooleanVar(value=False)
        ttk.Checkbutton(kinds, text="Any other file", variable=anyfile).pack(side="left", padx=8)
        state = ttk.Label(win, text="Enter a page address and press Explore.", style="Muted.TLabel")
        state.pack(anchor="w", padx=12)
        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=12, pady=4)
        res = ttk.Treeview(box, columns=("name", "type", "page"), show="headings", selectmode="extended", height=12)
        for k, t, w in (("name", "File name", 260), ("type", "Type", 60), ("page", "Found on", 340)):
            res.heading(k, text=t)
            res.column(k, width=w, anchor="w")
        sb = ttk.Scrollbar(box, orient="vertical", command=res.yview)
        res.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        res.pack(side="left", fill="both", expand=True)
        found, title, inbox = {}, {"t": ""}, queue.Queue()
        bottom = ttk.Frame(win)
        bottom.pack(fill="x", padx=12, pady=(4, 12))
        project = tk.StringVar()
        ttk.Label(bottom, text="Project name:").pack(side="left")
        ttk.Entry(bottom, textvariable=project, width=24).pack(side="left", padx=6)

        def explore():
            url = start.get().strip()
            if not url.lower().startswith(("http://", "https://")):
                return self.info("Site Grabber", "Enter an http:// or https:// address.", win)
            wanted = {e for c in self.mgr.settings["categories"] if c["name"] in checks and checks[c["name"]].get() for e in c["exts"]}
            if not wanted and not anyfile.get():
                return self.info("Site Grabber", "Tick at least one kind of file.", win)
            state.config(text="Exploring...")
            btn.state(["disabled"])
            deep = 1 if depth.get().startswith("This page and") else 0

            def work():
                try:
                    inbox.put(("ok", *grab_site(url, wanted, deep, anyfile.get())))
                except Exception as e:
                    inbox.put(("err", str(e)))
            threading.Thread(target=work, daemon=True).start()
            poll()

        def poll():
            try:
                msg = inbox.get_nowait()
            except queue.Empty:
                return win.after(150, poll) if win.winfo_exists() else None
            btn.state(["!disabled"])
            if msg[0] == "err":
                return state.config(text="Couldn't read that page: " + msg[1])
            res.delete(*res.get_children())
            found.clear()
            for n, f in enumerate(msg[1]):
                found[str(n)] = f
                res.insert("", "end", iid=str(n), values=(f["name"], f["ext"], f["page"]))
            res.selection_set(res.get_children())
            title["t"] = msg[2]
            project.set(project.get() or msg[2][:40] or urllib.parse.urlparse(start.get()).netloc)
            state.config(text=f"Found {len(found)} file(s). Select the ones you want." if found else "No matching files found on that page.")

        def grab(later):
            chosen = [found[i] for i in res.selection() if i in found]
            if not chosen:
                return self.info("Site Grabber", "Select at least one file.", win)
            name = project.get().strip() or urllib.parse.urlparse(start.get()).netloc
            for f in chosen:
                self.mgr.add(f["url"], self.folder.get(), self.conns.get(), queue=self.cur_queue(), project=name, later=later, referer=f["page"])
            state.config(text=f"Added {len(chosen)} download(s) to project '{name}'.")
            self.after_change()
        btn = ttk.Button(top, text="Explore", style="Accent.TButton", command=explore)
        btn.grid(row=1, column=2, padx=6)
        ttk.Button(bottom, text="Close", command=win.destroy).pack(side="right")
        ttk.Button(bottom, text="Download Later", command=lambda: grab(True)).pack(side="right", padx=6)
        ttk.Button(bottom, text="Start Download", style="Accent.TButton", command=lambda: grab(False)).pack(side="right")
        ttk.Button(bottom, text="Select none", command=lambda: res.selection_set(())).pack(side="right", padx=12)
        ttk.Button(bottom, text="Select all", command=lambda: res.selection_set(res.get_children())).pack(side="right")

    def export_list(self):
        p = filedialog.asksaveasfilename(parent=self.root, title="Export download list", defaultextension=".json", initialfile="aerograb-downloads.json",
                                         filetypes=[("AeroGrab list", "*.json"), ("All files", "*.*")])
        if p:
            self.flash(f"Exported {self.mgr.export_list(p)} download(s) to {p}")

    def import_list(self):
        p = filedialog.askopenfilename(parent=self.root, title="Import download list",
                                       filetypes=[("AeroGrab list or text with links", "*.json *.txt *.csv *.lst"), ("All files", "*.*")])
        if p:
            try:
                n = self.mgr.import_list(p, self.folder.get())
            except OSError as e:
                return messagebox.showerror("Import", str(e), parent=self.root)
            self.flash(f"Imported {n} download(s); they are stopped until you start them")
            self.after_change()

    # ------------------------------------------------------------------ dialogs: options, speed limiter, scheduler
    def text_dialog(self, title, text, width=78, height=22):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        t = tk.Text(box, width=width, height=height, wrap="word", padx=8, pady=6)
        sb = ttk.Scrollbar(box, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.insert("1.0", text)
        t.config(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=8)

    def options_dialog(self):
        st = self.mgr.settings
        win = tk.Toplevel(self.root)
        win.title("Options")
        win.transient(self.root)
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        v = {k: tk.BooleanVar(value=bool(st.get(k))) for k in ("tray", "close_to_tray", "notify", "start_minimized", "auto_sort", "show_complete_dialog", "confirm_captured")}
        folder, conns = tk.StringVar(value=self.folder.get()), tk.IntVar(value=self.conns.get())
        maxa, limit = tk.IntVar(value=self.mgr.max_active), tk.IntVar(value=self.limit_var.get())
        quality = tk.StringVar(value=str(st.get("quality") or "Best"))

        def group(parent, title):
            g = ttk.LabelFrame(parent, text=title, padding=8)
            g.pack(fill="x", pady=(0, 8))
            return g

        def textbox(parent, value, height):
            t = tk.Text(parent, width=70, height=height, wrap="word")
            t.insert("1.0", value)
            t.pack(anchor="w", pady=(2, 6))
            return t

        def read(t):
            return t.get("1.0", "end").strip()

        def choice(parent, key, options, default, label=None, width=46):
            """Dropdown with friendly labels; returns a getter for the stored value."""
            cur = st.get(key, default)
            var = tk.StringVar(value=options.get(cur, options[default]))
            if label:
                ttk.Label(parent, text=label).pack(anchor="w")
            ttk.Combobox(parent, textvariable=var, state="readonly", width=width, values=list(options.values())).pack(anchor="w", pady=(2, 8))
            return lambda: next((k for k, t in options.items() if t == var.get()), default)

        def folder_row(parent, label, var):
            ttk.Label(parent, text=label).pack(anchor="w")
            fr = ttk.Frame(parent)
            fr.pack(anchor="w", pady=(2, 8))
            ttk.Entry(fr, textvariable=var, width=58).pack(side="left")
            ttk.Button(fr, text="Browse...", command=lambda: var.set(filedialog.askdirectory(parent=win, initialdir=var.get() or None) or var.get())).pack(side="left", padx=6)

        gen = ttk.Frame(nb, padding=14)
        nb.add(gen, text="General")
        for key, text in (("tray", "Show an icon in the system tray"), ("close_to_tray", "Closing the window keeps AeroGrab running in the tray"),
                          ("notify", "Notify me when a download finishes or fails"), ("start_minimized", "Start minimized (to the tray if it is on)"),
                          ("show_complete_dialog", "Show the \"Download complete\" dialog when a download finishes"),
                          ("confirm_captured", "Ask before starting links sent from the browser")):
            ttk.Checkbutton(gen, text=text, variable=v[key]).pack(anchor="w", pady=3)
        gv = {k: tk.BooleanVar(value=bool(st.get(k, False))) for k in ("autostart", "clip_monitor")}
        gv["check_updates"] = tk.BooleanVar(value=bool(st.get("check_updates", True)))
        ttk.Checkbutton(gen, text="Launch AeroGrab when I sign in to the computer", variable=gv["autostart"]).pack(anchor="w", pady=3)
        ttk.Checkbutton(gen, text="Check for a new version of AeroGrab when it starts (GitHub)", variable=gv["check_updates"]).pack(anchor="w", pady=3)
        ttk.Checkbutton(gen, text="Automatically start downloading URLs placed on the clipboard (links to files only)", variable=gv["clip_monitor"]).pack(anchor="w", pady=3)
        ttk.Label(gen, wraplength=420, justify="left", style="Muted.TLabel",
                  text="The tray icon needs the optional add-on:  pip install pystray pillow  (Windows and Linux; not macOS).").pack(anchor="w", pady=(10, 0))

        sv = ttk.Frame(nb, padding=14)
        nb.add(sv, text="Save to")
        ttk.Label(sv, text="Default download folder:").pack(anchor="w")
        fr = ttk.Frame(sv)
        fr.pack(anchor="w", pady=(2, 10))
        ttk.Entry(fr, textvariable=folder, width=52).pack(side="left")
        ttk.Button(fr, text="Browse...", command=lambda: folder.set(filedialog.askdirectory(parent=win, initialdir=folder.get()) or folder.get())).pack(side="left", padx=6)
        ttk.Checkbutton(sv, text="Save each download in its category's folder (Video, Documents, ...)", variable=v["auto_sort"]).pack(anchor="w", pady=3)
        ttk.Button(sv, text="Edit categories...", command=self.categories_dialog).pack(anchor="w", pady=10)
        temp = tk.StringVar(value=str(st.get("temp_folder") or ""))
        folder_row(sv, "Temporary folder for streaming (HLS) downloads - empty = next to the file:", temp)
        dup_get = choice(sv, "dup_links", {"ask": "Ask me", "skip": "Ignore the new link", "add": "Add it again"}, "ask", label="If a link is already in the list:")
        exist_get = choice(sv, "file_exists", {"rename": "Add a number to the new file's name", "overwrite": "Replace the existing file"}, "rename",
                           label="If a file with the same name is already in the folder:")

        cn = ttk.Frame(nb, padding=14)
        nb.add(cn, text="Connection")
        for r, (label, var, lo, hi) in enumerate((("Connections per download (new downloads):", conns, 1, 32), ("Maximum simultaneous downloads:", maxa, 1, 10),
                                                   ("Speed limit in KBytes/sec (0 = unlimited):", limit, 0, 10_000_000))):
            ttk.Label(cn, text=label).grid(row=r, column=0, sticky="w", pady=5)
            ttk.Spinbox(cn, from_=lo, to=hi, width=9, textvariable=var).grid(row=r, column=1, padx=10)
        ttk.Label(cn, text="Video quality for HLS streams:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Combobox(cn, textvariable=quality, state="readonly", width=8, values=["Best", "1080", "720", "480", "360"]).grid(row=3, column=1, padx=10)

        br = ttk.Frame(nb, padding=14)
        nb.add(br, text="Browser")
        ttk.Label(br, wraplength=440, justify="left", text=(f"The browser extension talks to AeroGrab on 127.0.0.1:{self.port}"
                                                            + ("." if self.api_srv else " - but that port is busy right now; restart with  python aerograb.py -p 6801")
                                                            + "\nPaste this pairing token into the extension's options page:")).pack(anchor="w")
        e = ttk.Entry(br, width=52)
        e.insert(0, get_token())
        e.state(["readonly"])
        e.pack(anchor="w", pady=8)
        ttk.Button(br, text="Copy token", command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(get_token()))).pack(anchor="w")
        ttk.Button(br, text="Browser integration setup...", command=self.pairing_dialog).pack(anchor="w", pady=8)

        # ---- browser capture rules (the extension reads these from AeroGrab)
        cap = ttk.Frame(nb, padding=12)
        nb.add(cap, text="Capture")
        cl, cr = ttk.Frame(cap), ttk.Frame(cap)   # two columns so the tab stays short on small screens
        cl.pack(side="left", fill="y", anchor="n", padx=(0, 12))
        cr.pack(side="left", fill="y", anchor="n")
        cv = {k: tk.BooleanVar(value=bool(st.get(k, True))) for k in ("capture_downloads", "ctx_link", "ctx_media", "video_button")}
        g = group(cl, "Browser integration")
        ttk.Checkbutton(g, text="Capture downloads from browsers", variable=cv["capture_downloads"]).pack(anchor="w", pady=2)
        br_vars, cur_br = {}, (st.get("capture_browsers") if isinstance(st.get("capture_browsers"), dict) else {})
        g = group(cl, "Capture downloads from the following browsers")
        for key, label in BROWSER_NAMES:
            br_vars[key] = tk.BooleanVar(value=bool(cur_br.get(key, True)))
            ttk.Checkbutton(g, text=label, variable=br_vars[key]).pack(anchor="w", pady=2)
        g = group(cr, "Keys to prevent or force downloading with AeroGrab")
        key_labels = {"none": "None", "alt": "Alt", "ctrl": "Ctrl", "shift": "Shift"}
        k_prevent = choice(g, "key_prevent", key_labels, "alt", label="Hold this key while clicking to let\nthe browser download (not AeroGrab):", width=18)
        k_force = choice(g, "key_force", key_labels, "none", label="Hold this key while clicking to always\ndownload with AeroGrab (ignores file types):", width=18)
        g = group(cr, "In the browser")
        for key, text in (("ctx_link", "Show \"Download link with AeroGrab\" in the right-click menu"),
                          ("ctx_media", "Show \"Download media with AeroGrab\" in the right-click menu"),
                          ("video_button", "Show the \"Download this video\" button on playing videos")):
            ttk.Checkbutton(g, text=text, variable=cv[key]).pack(anchor="w", pady=2)

        # ---- file types
        ft = ttk.Frame(nb, padding=12)
        nb.add(ft, text="File types")
        ttk.Label(ft, text="Take over downloads of these file types (separate with spaces):").pack(anchor="w")
        t_cap = textbox(ft, st.get("capture_types", ""), 4)
        ttk.Label(ft, text="Never take over these (images and web page files, so page content is not captured):").pack(anchor="w")
        t_skip = textbox(ft, st.get("skip_types", ""), 3)
        v_unknown = tk.BooleanVar(value=bool(st.get("capture_unknown", True)))
        ttk.Checkbutton(ft, text="Also take over files whose type is in neither list (for example downloads without an extension)", variable=v_unknown).pack(anchor="w", pady=2)
        ttk.Label(ft, text="Don't take over downloads from these sites (one per line, * allowed):").pack(anchor="w", pady=(8, 0))
        t_sites = textbox(ft, st.get("exclude_sites", ""), 3)
        minkb = tk.IntVar(value=int(st.get("min_size_kb") or 0))
        mrow = ttk.Frame(ft)
        mrow.pack(anchor="w")
        ttk.Label(mrow, text="Ignore browser downloads smaller than (KB, 0 = off):").pack(side="left")
        ttk.Spinbox(mrow, from_=0, to=10_000_000, width=9, textvariable=minkb).pack(side="left", padx=8)

        def reset_types():
            for box, key in ((t_cap, "capture_types"), (t_skip, "skip_types")):
                box.delete("1.0", "end")
                box.insert("1.0", DEFAULT_SETTINGS[key])
        ttk.Button(ft, text="Reset lists to defaults", command=reset_types).pack(anchor="w", pady=(8, 0))

        # ---- automatic retry (on the Connection tab)
        retry_on, retry_n = tk.BooleanVar(value=bool(st.get("auto_retry", True))), tk.IntVar(value=int(st.get("retry_max", 5) or 0))
        ttk.Checkbutton(cn, text="Retry failed downloads automatically (network errors, busy servers)", variable=retry_on).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 2))
        ttk.Label(cn, text="Give up after this many retries:").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Spinbox(cn, from_=1, to=50, width=9, textvariable=retry_n).grid(row=5, column=1, padx=10)
        ttk.Label(cn, wraplength=440, justify="left", style="Muted.TLabel",
                  text="Retries wait longer each time (15 s, 30 s, 1 min ...) and pause while the internet is down. Wrong passwords and missing files are never retried.").grid(row=6, column=0, columnspan=2, sticky="w")

        timeout, retries = tk.IntVar(value=int(st.get("timeout") or 30)), tk.IntVar(value=int(st.get("retries", 6)))
        for r, (label, var, lo, hi) in enumerate((("Connection timeout in seconds:", timeout, 5, 300), ("Retries per connection before it gives up:", retries, 0, 30)), 7):
            ttk.Label(cn, text=label).grid(row=r, column=0, sticky="w", pady=5)
            ttk.Spinbox(cn, from_=lo, to=hi, width=9, textvariable=var).grid(row=r, column=1, padx=10)

        # ---- proxy
        px = ttk.Frame(nb, padding=14)
        nb.add(px, text="Proxy")
        pmode, ptype = tk.StringVar(value=st.get("proxy_mode", "system")), tk.StringVar(value=st.get("proxy_type", "http"))
        pv = {k: tk.StringVar(value=str(st.get(k) or "")) for k in ("proxy_host", "proxy_port", "proxy_user", "proxy_pass", "proxy_bypass")}
        for r, (val, text) in enumerate((("system", "Use the system proxy settings (default)"), ("none", "Connect directly (no proxy)"), ("manual", "Use this proxy:"))):
            ttk.Radiobutton(px, text=text, value=val, variable=pmode).grid(row=r, column=0, columnspan=2, sticky="w", pady=2)
        pf = ttk.Frame(px)
        pf.grid(row=3, column=0, columnspan=2, sticky="w", padx=(24, 0), pady=(2, 8))
        ttk.Label(pf, text="Type:").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=3)
        ttk.Combobox(pf, textvariable=ptype, state="readonly", width=10, values=["http", "socks5"]).grid(row=0, column=1, sticky="w")
        for r, (label, key, hide) in enumerate((("Host:", "proxy_host", ""), ("Port:", "proxy_port", ""), ("User name:", "proxy_user", ""), ("Password:", "proxy_pass", "*")), 1):
            ttk.Label(pf, text=label).grid(row=r, column=0, sticky="e", padx=(0, 6), pady=3)
            ttk.Entry(pf, textvariable=pv[key], width=8 if key == "proxy_port" else 34, show=hide).grid(row=r, column=1, sticky="w")
        ttk.Label(px, text="Don't use the proxy for (example.com, *.corp.test, 10.0.0.0/8):").grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Entry(px, textvariable=pv["proxy_bypass"], width=58).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 8))
        ptest = ttk.Label(px, text="", wraplength=440, justify="left")

        def proxy_settings():
            try:
                port = max(0, min(65535, int(pv["proxy_port"].get() or 0)))
            except ValueError:
                port = 0
            return {"proxy_mode": "manual", "proxy_type": ptype.get(), "proxy_host": pv["proxy_host"].get().strip(), "proxy_port": port,
                    "proxy_user": pv["proxy_user"].get(), "proxy_pass": pv["proxy_pass"].get(), "proxy_bypass": pv["proxy_bypass"].get()}

        def try_proxy():
            cfg = proxy_settings()
            if not cfg["proxy_host"]:
                return ptest.config(text="Enter the proxy's host first.")
            ptest.config(text="Testing (needs internet access)...")
            res = {}
            threading.Thread(target=lambda: res.update(r=check_proxy(cfg)), daemon=True).start()

            def poll():
                if "r" in res:
                    ptest.config(text=("OK - " if res["r"][0] else "Failed - ") + res["r"][1])
                elif win.winfo_exists():
                    win.after(200, poll)
            poll()
        ttk.Button(px, text="Test proxy", command=try_proxy).grid(row=6, column=0, sticky="w")
        ptest.grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(px, wraplength=440, justify="left", style="Muted.TLabel",
                  text="HTTP proxies carry HTTP and HTTPS downloads. SOCKS5 looks names up on the proxy. FTP, local addresses and (for ffmpeg) SOCKS bypass this setting. "
                       "The password is stored in AeroGrab's settings file, readable only by you.").grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # ---- site logins
        lg = ttk.Frame(nb, padding=14)
        nb.add(lg, text="Logins")
        logins = [dict(x) for x in st.get("site_logins", []) if isinstance(x, dict) and x.get("host")]
        ttk.Label(lg, wraplength=440, justify="left", text="User name and password for sites that ask for them (HTTP/HTTPS login prompts and FTP). "
                                                           "They are given only to the site named here. You can also put them in the link: ftp://name:password@host/file").pack(anchor="w")
        lv = ttk.Treeview(lg, columns=("host", "user"), show="headings", height=7, selectmode="browse")
        lv.heading("host", text="Site")
        lv.heading("user", text="User name")
        lv.column("host", width=260)
        lv.column("user", width=160)
        lv.pack(fill="x", pady=8)

        def refill():
            lv.delete(*lv.get_children())
            for i, x in enumerate(logins):
                lv.insert("", "end", iid=str(i), values=(x["host"], x.get("user", "")))

        def edit_login(new):
            sel = lv.selection()
            if not new and not sel:
                return
            cur = {"host": "", "user": "", "pass": ""} if new else logins[int(sel[0])]
            host = simpledialog.askstring("Login", "Site (for example files.example.com):", parent=win, initialvalue=cur["host"])
            if not host or not host.strip():
                return
            user = simpledialog.askstring("Login", "User name:", parent=win, initialvalue=cur.get("user", ""))
            if user is None:
                return
            pw = simpledialog.askstring("Login", "Password:", parent=win, show="*", initialvalue=cur.get("pass", ""))
            if pw is None:
                return
            entry = {"host": _host_of(host.strip()) or host.strip().lower(), "user": user, "pass": pw}
            logins[:] = [x for x in logins if x["host"] != entry["host"] and x is not cur] + [entry]
            refill()

        def del_login():
            sel = lv.selection()
            if sel:
                del logins[int(sel[0])]
                refill()
        lb = ttk.Frame(lg)
        lb.pack(anchor="w")
        ttk.Button(lb, text="Add...", command=lambda: edit_login(True)).pack(side="left", padx=(0, 6))
        ttk.Button(lb, text="Edit...", command=lambda: edit_login(False)).pack(side="left", padx=6)
        ttk.Button(lb, text="Remove", command=del_login).pack(side="left", padx=6)
        refill()

        # ---- appearance
        ap = ttk.Frame(nb, padding=14)
        nb.add(ap, text="Appearance")
        theme = tk.StringVar(value={"light": "Light", "dark": "Dark", "system": "System"}.get(st.get("theme", "dark"), "Dark"))
        accent = tk.StringVar(value=valid_hex(st.get("accent")) or DEFAULT_ACCENT)
        ttk.Label(ap, text="Theme:").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Combobox(ap, textvariable=theme, state="readonly", width=12, values=["Dark", "Light", "System"]).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(ap, text="Accent colour:").grid(row=1, column=0, sticky="w", pady=6)
        sw = ttk.Frame(ap)
        sw.grid(row=1, column=1, sticky="w", padx=10)
        prev = tk.Label(ap, width=34, relief="solid", bd=1)
        prev.grid(row=2, column=1, sticky="w", padx=10, pady=4)

        def show_accent(*_):
            c = valid_hex(accent.get()) or DEFAULT_ACCENT
            prev.config(bg=c, fg=contrast_fg(c), text=f"{c}  (selected / progress colour)")
        accent.trace_add("write", show_accent)
        show_accent()
        for name, c in ACCENTS:
            b = tk.Label(sw, bg=c, width=3, relief="solid", bd=1, cursor="hand2")
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, c=c: accent.set(c))

        def custom_accent():
            from tkinter import colorchooser
            got = colorchooser.askcolor(color=accent.get(), parent=win, title="Accent colour")
            if got and got[1]:
                accent.set(got[1])
        ttk.Button(ap, text="Other colour...", command=custom_accent).grid(row=3, column=1, sticky="w", padx=10)
        skin = tk.StringVar(value=(st.get("skin") if st.get("skin") in SKINS else "default").title())
        ttk.Label(ap, text="Skin:").grid(row=4, column=0, sticky="w", pady=(14, 6))
        ttk.Combobox(ap, textvariable=skin, state="readonly", width=16, values=[n.title() for n in skin_names()]).grid(row=4, column=1, sticky="w", padx=10, pady=(14, 6))
        ttk.Label(ap, text="Toolbar:").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Button(ap, text="Customize toolbar...", command=self.customize_toolbar).grid(row=5, column=1, sticky="w", padx=10)
        ttk.Label(ap, wraplength=440, justify="left", style="Muted.TLabel",
                  text="Dark and Light are the two AeroGrab Premium themes; System follows your operating system's light / dark setting. You can also switch from the sun / moon button in the header or from View > Theme. "
                       "A skin is an alternative colour scheme: it replaces Theme (and its own accent colour is used unless you pick one above). Changes apply when you press OK.").grid(row=6, column=0, columnspan=2, sticky="w", pady=(14, 0))

        # ---- sounds
        so = ttk.Frame(nb, padding=14)
        nb.add(so, text="Sounds")
        s_on = tk.BooleanVar(value=bool(st.get("sound", True)))
        ttk.Checkbutton(so, text="Play sounds", variable=s_on).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        ev_on = {ev: tk.BooleanVar(value=bool(st.get("sound_" + ev, True))) for ev, _ in SOUND_EVENTS}
        ev_file = {ev: tk.StringVar(value=(st.get("sound_files") or {}).get(ev, "")) for ev, _ in SOUND_EVENTS}
        for r, (ev, label) in enumerate(SOUND_EVENTS, 1):
            ttk.Checkbutton(so, text=label, variable=ev_on[ev]).grid(row=2 * r - 1, column=0, columnspan=4, sticky="w")
            ttk.Entry(so, textvariable=ev_file[ev], width=34).grid(row=2 * r, column=0, columnspan=2, sticky="w", padx=(22, 4), pady=(0, 6))
            ttk.Button(so, text="Browse...", command=lambda v=ev_file[ev]: v.set(filedialog.askopenfilename(parent=win, title="Sound file", filetypes=[("Sound", "*.wav *.ogg *.oga *.mp3 *.aiff"), ("All files", "*.*")]) or v.get())).grid(row=2 * r, column=2, pady=(0, 6))
            ttk.Button(so, text="Test", command=lambda e=ev, v=ev_file[ev]: self.test_sound(e, v.get().strip())).grid(row=2 * r, column=3, padx=4, pady=(0, 6))
        s_focus = tk.BooleanVar(value=bool(st.get("sound_unfocused_only")))
        s_quiet = tk.BooleanVar(value=bool(st.get("sound_quiet")))
        q_from, q_to = tk.StringVar(value=st.get("sound_quiet_from", "22:00")), tk.StringVar(value=st.get("sound_quiet_to", "07:00"))
        ttk.Checkbutton(so, text="Only when AeroGrab is not the window in front", variable=s_focus).grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 2))
        qr = ttk.Frame(so)
        qr.grid(row=9, column=0, columnspan=4, sticky="w")
        ttk.Checkbutton(qr, text="Quiet hours, no sound from", variable=s_quiet).pack(side="left")
        ttk.Entry(qr, textvariable=q_from, width=6).pack(side="left", padx=4)
        ttk.Label(qr, text="to").pack(side="left")
        ttk.Entry(qr, textvariable=q_to, width=6).pack(side="left", padx=4)
        ttk.Label(so, wraplength=440, justify="left", style="Muted.TLabel",
                  text="When several things happen at once only the most important sound plays. Leave a file box empty to use the system sound (Windows: .wav files only).").grid(row=10, column=0, columnspan=4, sticky="w", pady=(10, 0))

        # ---- extras: antivirus, smart links, clipboard history, floating widget
        ex = ttk.Frame(nb, padding=14)
        nb.add(ex, text="Extras")
        av_names = {"Automatic": "auto", "Windows Defender": "defender", "ClamAV": "clamav"}
        av_on, av_eng = tk.BooleanVar(value=bool(st.get("av_scan", True))), tk.StringVar(value=next((k for k, x in av_names.items() if x == st.get("av_engine")), "Automatic"))
        ttk.Checkbutton(ex, text="Scan finished downloads with the antivirus installed on this computer", variable=av_on).pack(anchor="w")
        avr = ttk.Frame(ex)
        avr.pack(anchor="w", pady=(4, 0))
        ttk.Label(avr, text="Scanner:").pack(side="left")
        ttk.Combobox(avr, textvariable=av_eng, state="readonly", width=18, values=list(av_names)).pack(side="left", padx=6)
        av_det = ttk.Label(ex, wraplength=440, justify="left")
        av_det.pack(anchor="w", pady=(4, 0))

        def av_status(*_):
            f = find_av(av_names.get(av_eng.get(), "auto"))
            av_det.config(text=f"Found: {AV_NAMES[f[0]]}  ({f[1]})" if f else "No antivirus found. Windows Defender and ClamAV are the two AeroGrab can use.", style="Success.TLabel" if f else "Warning.TLabel")
        av_eng.trace_add("write", av_status)
        av_status()
        ttk.Label(ex, wraplength=440, justify="left", style="Muted.TLabel",
                  text="AeroGrab includes no antivirus engine. It runs Windows Defender (MpCmdRun.exe -Scan) or ClamAV (clamscan) and shows the verdict in the Download complete window. "
                       "It only checks: nothing is deleted or quarantined by AeroGrab.").pack(anchor="w", pady=(2, 0))
        ttk.Separator(ex).pack(fill="x", pady=10)
        su, cw, wd = (tk.BooleanVar(value=bool(st.get(k))) for k in ("smart_unwrap", "clip_watch", "widget_on"))
        ttk.Checkbutton(ex, text="Take redirect wrappers off pasted links (google.com/url?q=..., facebook l.php?u=...)", variable=su).pack(anchor="w", pady=2)
        ttk.Checkbutton(ex, text="Keep a history of links I copy (Tasks > Clipboard history); only web / FTP addresses are kept", variable=cw).pack(anchor="w", pady=2)
        ttk.Checkbutton(ex, text="Show the floating widget (a small always-on-top speed meter)", variable=wd).pack(anchor="w", pady=2)
        opr = ttk.Frame(ex)
        opr.pack(anchor="w", pady=(2, 0))
        ttk.Label(opr, text="Widget opacity (%):").pack(side="left")
        wa = tk.IntVar(value=int(st.get("widget_alpha") or 90))
        ttk.Spinbox(opr, from_=30, to=100, increment=10, textvariable=wa, width=5).pack(side="left", padx=6)

        def num(var, lo, hi, default):
            try:
                return max(lo, min(hi, int(var.get())))
            except (tk.TclError, ValueError):
                return default

        def ok():
            if pmode.get() == "manual" and not pv["proxy_host"].get().strip():
                nb.select(px)
                return messagebox.showerror("Proxy", "Enter the proxy's host, or choose 'Use the system proxy settings'.", parent=win)
            try:
                parse_hm(q_from.get())
                parse_hm(q_to.get())
            except ValueError:
                nb.select(so)
                return messagebox.showerror("Sounds", "Quiet hours must look like 22:00 and 07:00.", parent=win)
            f = folder.get().strip()
            if f:
                self.folder.set(f)
                st["folder"] = f
            self.conns.set(num(conns, 1, 32, 8))
            st["connections"] = self.conns.get()
            self.mgr.max_active = st["max_active"] = num(maxa, 1, 10, 3)
            self.limit_var.set(num(limit, 0, 10_000_000, 0))
            st["quality"] = 0 if quality.get() == "Best" else int(quality.get())
            st["auto_sort"] = v["auto_sort"].get()
            want = v["tray"].get()
            if want != bool(self.tray):
                err = self.set_tray(want)
                if err and want:
                    messagebox.showinfo("System tray", err, parent=win)
                    want = False
            st.update(tray=want, close_to_tray=v["close_to_tray"].get(), notify=v["notify"].get(), start_minimized=v["start_minimized"].get(),
                      show_complete_dialog=v["show_complete_dialog"].get(), confirm_captured=v["confirm_captured"].get())
            st["auto_retry"], st["retry_max"] = retry_on.get(), num(retry_n, 1, 50, 5)
            px_new = proxy_settings()
            st.update(proxy_mode=pmode.get(), proxy_type=px_new["proxy_type"], proxy_host=px_new["proxy_host"], proxy_port=px_new["proxy_port"],
                      proxy_user=px_new["proxy_user"], proxy_pass=px_new["proxy_pass"], proxy_bypass=px_new["proxy_bypass"].strip(),
                      site_logins=logins, theme=theme.get().lower(), accent=valid_hex(accent.get()) or DEFAULT_ACCENT,
                      sound=s_on.get(), sound_unfocused_only=s_focus.get(), sound_quiet=s_quiet.get(), sound_quiet_from=q_from.get().strip(),
                      sound_quiet_to=q_to.get().strip(), sound_files={e: v.get().strip() for e, v in ev_file.items() if v.get().strip()},
                      **{"sound_" + e: v.get() for e, v in ev_on.items()})
            was_watching = bool(st.get("clip_watch"))
            st.update(skin=skin.get().lower(), av_scan=av_on.get(), av_engine=av_names.get(av_eng.get(), "auto"), smart_unwrap=su.get(), clip_watch=cw.get(), widget_alpha=num(wa, 30, 100, 90))
            if cw.get() and not was_watching:
                self._clip_last = None  # whatever is on the clipboard right now was not copied "just now"
            if wd.get() != self.widget.shown:
                self.toggle_widget(wd.get())
            else:
                self.widget.set_alpha()
            st["timeout"], st["retries"] = num(timeout, 5, 300, 30), num(retries, 0, 30, 6)
            st["temp_folder"] = temp.get().strip()
            st.update(capture_downloads=cv["capture_downloads"].get(), clip_monitor=gv["clip_monitor"].get(), ctx_link=cv["ctx_link"].get(), ctx_media=cv["ctx_media"].get(),
                      video_button=cv["video_button"].get(), capture_browsers={k: x.get() for k, x in br_vars.items()}, key_prevent=k_prevent(), key_force=k_force(),
                      capture_types=" ".join(split_list(read(t_cap))), skip_types=" ".join(split_list(read(t_skip))), capture_unknown=v_unknown.get(),
                      exclude_sites=read(t_sites), min_size_kb=num(minkb, 0, 10_000_000, 0), dup_links=dup_get(), file_exists=exist_get(),
                      )
            st["check_updates"] = gv["check_updates"].get()
            self._autoclip_last = None  # whatever is on the clipboard right now was not copied "just now"
            want_auto = gv["autostart"].get()
            if want_auto != bool(st.get("autostart")):
                err = set_autostart(want_auto)
                if err:
                    messagebox.showinfo("Start with the computer", f"Couldn't change the start-up setting:\n{err}", parent=win)
                    want_auto = bool(st.get("autostart"))
            st["autostart"] = want_auto
            self.mgr.apply_network()  # proxy, logins and timeouts take effect for the next connection
            self.apply_theme()
            self.mgr.save_settings()
            win.destroy()
            self.flash("Options saved")
        row = ttk.Frame(win)
        row.pack(pady=(4, 12))
        ttk.Button(row, text="OK", style="Accent.TButton", command=ok).pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    def speed_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Speed limiter")
        win.transient(self.root)
        on, kb = tk.BooleanVar(value=self.limit_var.get() > 0), tk.IntVar(value=self.limit_var.get() or 512)
        ttk.Checkbutton(win, text="Use speed limiter", variable=on).pack(anchor="w", padx=14, pady=(14, 6))
        row = ttk.Frame(win)
        row.pack(padx=14, anchor="w")
        ttk.Label(row, text="Maximum download speed (KBytes/sec):").pack(side="left")
        ttk.Spinbox(row, from_=1, to=10_000_000, width=9, textvariable=kb).pack(side="left", padx=8)

        def ok():
            try:
                self.limit_var.set(max(1, int(kb.get())) if on.get() else 0)
            except (tk.TclError, ValueError):
                return
            win.destroy()
        r2 = ttk.Frame(win)
        r2.pack(pady=14)
        ttk.Button(r2, text="OK", style="Accent.TButton", command=ok).pack(side="left", padx=6)
        ttk.Button(r2, text="Cancel", command=win.destroy).pack(side="left", padx=6)

    def scheduler_dialog(self):
        st = self.mgr.settings
        win = tk.Toplevel(self.root)
        win.title("Scheduler")
        win.transient(self.root)
        on, a, b = tk.BooleanVar(value=st["sched_on"]), tk.StringVar(value=st["start"]), tk.StringVar(value=st["stop"])
        after = tk.StringVar(value=AFTER[st["after"]])
        ttk.Checkbutton(win, text="Only download between these times (24-hour HH:MM)", variable=on).pack(anchor="w", padx=12, pady=(12, 4))
        row = ttk.Frame(win)
        row.pack(anchor="w", padx=12)
        ttk.Label(row, text="From").pack(side="left")
        ttk.Entry(row, textvariable=a, width=6).pack(side="left", padx=4)
        ttk.Label(row, text="to").pack(side="left")
        ttk.Entry(row, textvariable=b, width=6).pack(side="left", padx=4)
        ttk.Label(win, text="When all downloads finish (one time):").pack(anchor="w", padx=12, pady=(12, 2))
        ttk.Combobox(win, textvariable=after, values=list(AFTER.values()), state="readonly").pack(anchor="w", padx=12)

        def ok():
            try:
                parse_hm(a.get())
                parse_hm(b.get())
            except ValueError:
                return messagebox.showerror("Scheduler", "Times must look like 01:30", parent=win)
            st.update(sched_on=on.get(), start=a.get().strip(), stop=b.get().strip(), after=[k for k, x in AFTER.items() if x == after.get()][0])
            self.mgr.save_settings()
            win.destroy()
        ttk.Button(win, text="Save", style="Accent.TButton", command=ok).pack(pady=12)

    def countdown(self, sec=60):
        win = tk.Toplevel(self.root)
        win.title("Shutting down")
        lab = ttk.Label(win, padding=15)
        lab.pack()
        state = {"n": sec}
        ttk.Button(win, text="Cancel shutdown", command=win.destroy).pack(pady=8)

        def step():
            if state["n"] <= 0:
                self.mgr.shutdown()
                power_off()
                return self.root.destroy()
            lab.config(text=f"All downloads finished.\nShutting down the computer in {state['n']} s")
            state["n"] -= 1
            win.after(1000, step)
        step()

    def after_done(self):
        """Runs the one-time 'when finished' action. Returns True if the app is closing."""
        act, self.mgr.settings["after"] = self.mgr.settings["after"], "none"
        self.mgr.save_settings()
        if act == "exit":
            self.on_close()
            return True
        if act == "shutdown":
            self.countdown()
        return False

    # ------------------------------------------------------------------ dialogs: categories
    def categories_dialog(self):
        mgr = self.mgr
        win = tk.Toplevel(self.root)
        win.title("Categories")
        win.transient(self.root)
        orig = [c["name"] for c in mgr.settings["categories"]]
        cats = [dict(c, _was=c["name"]) for c in copy.deepcopy(mgr.settings["categories"])]  # edit a copy; OK applies it
        auto = tk.BooleanVar(value=mgr.settings.get("auto_sort", True))
        name, exts, fold, sites = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        cur, entries = {"i": 0}, {}
        left = ttk.Frame(win)
        left.pack(side="left", fill="y", padx=(10, 6), pady=10)
        lb = tk.Listbox(left, width=20, height=13, exportselection=False)
        lb.pack(fill="y", expand=True)
        right = ttk.Frame(win)
        right.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        def field(label, var, key):
            ttk.Label(right, text=label).pack(anchor="w")
            entries[key] = ttk.Entry(right, textvariable=var, width=54)
            entries[key].pack(anchor="w", pady=(0, 7))
        field("Name", name, "name")
        field("File types (comma separated, e.g. mp4, mkv)", exts, "exts")
        ttk.Label(right, text="Save to (empty = <download folder>/<name>)").pack(anchor="w")
        fr = ttk.Frame(right)
        fr.pack(anchor="w", pady=(0, 7))
        entries["folder"] = ttk.Entry(fr, textvariable=fold, width=44)
        entries["folder"].pack(side="left")
        ttk.Button(fr, text="Browse...", command=lambda: fold.set(filedialog.askdirectory(parent=win) or fold.get())).pack(side="left", padx=4)
        field("Websites (comma separated, e.g. school.example): these always go here", sites, "sites")
        ttk.Checkbutton(right, text="Automatically save downloads into their category's folder", variable=auto).pack(anchor="w", pady=(6, 0))
        ttk.Label(right, text="Override one download any time: right-click it > Move to category.", style="Muted.TLabel").pack(anchor="w")

        def clean_site(x):
            x = re.sub(r"^https?://", "", x.strip().lower())
            return re.sub(r"^www\.", "", x).split("/")[0]

        def show(i):
            cur["i"] = i
            c = cats[i]
            name.set(c["name"])
            exts.set(", ".join(c["exts"]))
            fold.set(c["folder"])
            sites.set(", ".join(c["sites"]))
            general = c["name"] == "General"  # the catch-all can't be renamed or given file types
            entries["name"].config(state="disabled" if general else "normal")
            entries["exts"].config(state="disabled" if general else "normal")
            lb.selection_clear(0, "end")
            lb.selection_set(i)
            lb.see(i)

        def fill():
            lb.delete(0, "end")
            for c in cats:
                lb.insert("end", c["name"])

        def commit():
            c, n = cats[cur["i"]], name.get().strip()
            if c["name"] != "General":
                if not n or len(n) > 40 or any(ch in n for ch in '/\\:*?"<>|'):
                    return messagebox.showerror("Categories", 'Give it a short name without  / \\ : * ? " < > |', parent=win) and False
                if any(k != cur["i"] and x["name"].lower() == n.lower() for k, x in enumerate(cats)):
                    return messagebox.showerror("Categories", f"There is already a category called {n!r}.", parent=win) and False
                c["name"] = n
                c["exts"] = sorted({e.lstrip(".").lower() for e in re.split(r"[,\s]+", exts.get()) if e.lstrip(".").isalnum()})
            c["folder"] = fold.get().strip()
            c["sites"] = sorted({clean_site(x) for x in re.split(r"[,\s]+", sites.get()) if clean_site(x)})
            lb.delete(cur["i"])
            lb.insert(cur["i"], c["name"])
            lb.selection_set(cur["i"])
            return True

        def pick(_=None):
            sel = lb.curselection()
            if sel and sel[0] != cur["i"]:
                old = cur["i"]
                if commit():
                    show(sel[0])
                else:
                    lb.selection_clear(0, "end")
                    lb.selection_set(old)
        lb.bind("<<ListboxSelect>>", pick)

        def new():
            if commit():
                n, k = "New category", 1
                while any(c["name"].lower() == n.lower() for c in cats):
                    k += 1
                    n = f"New category {k}"
                cats.append({"name": n, "exts": [], "folder": "", "sites": []})
                fill()
                show(len(cats) - 1)

        def delete():
            if cats[cur["i"]]["name"] == "General":
                return messagebox.showinfo("Categories", "General is the catch-all and can't be deleted.", parent=win)
            del cats[cur["i"]]
            fill()
            show(min(cur["i"], len(cats) - 1))

        def reset():
            if messagebox.askyesno("Categories", "Replace the list with the built-in categories?", parent=win):
                cats[:] = [dict(c, _was=c["name"]) for c in copy.deepcopy(DEFAULT_CATEGORIES)]
                fill()
                show(0)

        def ok():
            if not commit():
                return
            kept = {c.get("_was") for c in cats}
            renames = {c["_was"]: c["name"] for c in cats if c.get("_was") and c["_was"] != c["name"]}
            for d in mgr.items:  # keep existing downloads pointing at real categories
                if d.category in renames:
                    d.category = renames[d.category]
                elif d.category in orig and d.category not in kept:
                    d.category, d.auto_cat = "General", True
            mgr.settings["categories"] = [{k: x for k, x in c.items() if k != "_was"} for c in cats]
            mgr.settings["auto_sort"] = auto.get()
            mgr._fix_categories()
            mgr.save_settings()
            win.destroy()
            self.after_change()
        ttk.Button(left, text="New category", command=new).pack(fill="x", pady=(6, 0))
        ttk.Button(left, text="Delete", command=delete).pack(fill="x", pady=(4, 0))
        ttk.Button(left, text="Reset to defaults", command=reset).pack(fill="x", pady=(4, 0))
        row = ttk.Frame(right)
        row.pack(anchor="e", pady=(14, 0), fill="x")
        ttk.Button(row, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(row, text="OK", style="Accent.TButton", command=ok).pack(side="right", padx=6)
        fill()
        show(0)

    # ------------------------------------------------------------------ dialogs: browser pairing, help, registration
    def native(self):
        return NativeIntegration(self.mgr.settings.get("extension_ids", []))

    def register_browsers(self, silent=False):
        """Register AeroGrab's native-messaging host with every installed browser (Windows: in the registry under HKCU)."""
        try:
            res = self.native().register()
        except Exception as e:  # e.g. registry locked down by policy, read-only profile folder
            self.flash(f"Browser integration failed: {e}", 20)
            if not silent:
                messagebox.showerror("Browser integration", f"Couldn't register with the browsers:\n{e}", parent=self.root)
            return []
        ok = [r["label"] for r in res if r["registered"]]
        self.flash("Browser integration ready for " + ", ".join(ok) if ok else "Browser integration: no supported browser found yet", 10)
        return res

    def pairing_dialog(self):
        """Browser integration: status per browser, register/repair/remove, and the manual token as a last resort."""
        st = self.mgr.settings
        win = tk.Toplevel(self.root)
        win.title("Browser integration")
        win.transient(self.root)
        where = "the Windows registry (HKCU, current user only)" if platform.system() == "Windows" else "each browser's NativeMessagingHosts folder"
        ttk.Label(win, wraplength=560, justify="left", text=("AeroGrab registers itself with your browsers in " + where + ", so the AeroGrab extension "
                  "sends downloads straight to it: no port numbers, no tokens. Only the extension IDs listed below are allowed to talk to AeroGrab.")).pack(padx=14, pady=(14, 8), anchor="w")
        tv = ttk.Treeview(win, columns=("browser", "state"), show="headings", height=5)
        tv.heading("browser", text="Browser")
        tv.heading("state", text="Status")
        tv.column("browser", width=170)
        tv.column("state", width=380)
        tv.pack(padx=14, fill="x")
        names = {"registered": "Registered \u2714", "outdated": "Out of date - press Register / Repair", "not registered": "Not registered",
                 "browser not found": "Browser not found"}

        def refresh():
            tv.delete(*tv.get_children())
            for r in self.native().status():
                tv.insert("", "end", values=(r["label"], names[r["state"]]))

        def register():
            self.register_browsers()
            refresh()

        def remove():
            if messagebox.askyesno("Browser integration", "Remove AeroGrab's registration from all browsers?\nThe extension will then need the manual token.", parent=win):
                self.native().unregister()
                refresh()
        row = ttk.Frame(win)
        row.pack(padx=14, pady=8, anchor="w")
        ttk.Button(row, text="Register / Repair", command=register).pack(side="left")
        ttk.Button(row, text="Remove registration", command=remove).pack(side="left", padx=6)
        ttk.Button(row, text="Refresh", command=refresh).pack(side="left")
        v_auto, v_start = tk.BooleanVar(value=st.get("native_register", True)), tk.BooleanVar(value=st.get("autostart_from_browser", True))

        def flags():
            st.update(native_register=v_auto.get(), autostart_from_browser=v_start.get())
            self.mgr.save_settings()
        ttk.Checkbutton(win, text="Register automatically every time AeroGrab starts", variable=v_auto, command=flags).pack(padx=14, anchor="w")
        ttk.Checkbutton(win, text="Start AeroGrab when the browser sends a download and it isn't running", variable=v_start, command=flags).pack(padx=14, anchor="w")
        ttk.Separator(win).pack(fill="x", padx=14, pady=10)
        ttk.Label(win, text="Extension ID built into this AeroGrab (load the extension folder as an unpacked extension):").pack(padx=14, anchor="w")
        built = ttk.Entry(win, width=60)
        built.insert(0, DEFAULT_EXTENSION_IDS[0])
        built.state(["readonly"])
        built.pack(padx=14, anchor="w", pady=(2, 8))
        ttk.Label(win, text="Also trust these extension IDs (comma separated, e.g. a Chrome Web Store ID):").pack(padx=14, anchor="w")
        ids = tk.StringVar(value=", ".join(st.get("extension_ids", [])))
        r2 = ttk.Frame(win)
        r2.pack(padx=14, anchor="w", pady=(2, 0))
        ttk.Entry(r2, textvariable=ids, width=52).pack(side="left")

        def save_ids():
            wanted = [x.lower() for x in re.split(r"[,\s]+", ids.get()) if x]
            good = [i for i in extension_ids(wanted) if i not in DEFAULT_EXTENSION_IDS]
            bad = [x for x in wanted if x not in good and x not in DEFAULT_EXTENSION_IDS]
            if bad:
                return messagebox.showerror("Browser integration", "An extension ID is 32 letters from a to p. Not valid: " + ", ".join(bad), parent=win)
            st["extension_ids"] = good
            self.mgr.save_settings()
            register()
        ttk.Button(r2, text="Save", style="Accent.TButton", command=save_ids).pack(side="left", padx=6)
        ttk.Separator(win).pack(fill="x", padx=14, pady=10)
        ttk.Label(win, style="Muted.TLabel", wraplength=560, justify="left", text=(
            f"Advanced - manual pairing, only if automatic registration can't be used. Server: 127.0.0.1:{self.port}"
            + ("" if self.api_srv else " (PORT BUSY: restart with  python aerograb.py -p 6801)") + ". Pairing token:")).pack(padx=14, anchor="w")
        r3 = ttk.Frame(win)
        r3.pack(padx=14, anchor="w", pady=(2, 14))
        e = ttk.Entry(r3, width=52)
        e.insert(0, get_token())
        e.state(["readonly"])
        e.pack(side="left")
        ttk.Button(r3, text="Copy token", command=lambda: (self.root.clipboard_clear(), self.root.clipboard_append(get_token()))).pack(side="left", padx=6)
        refresh()

    def help_dialog(self):
        self.text_dialog("Quick help", """ADDING DOWNLOADS
  Tasks > Add new download (Ctrl+N), or copy links and use "Add batch download from clipboard".
  With the browser extension installed, downloads and videos on web pages are sent to AeroGrab automatically.
  Tasks > Run site grabber scans a page for files (images, videos, documents...) and adds the ones you pick as a project.

THE LEFT PANE
  All Downloads  - every download, with the categories (Video, Documents, ...) below it.
  Unfinished / Finished - what is still running or stopped, and what is done.
  Grabber projects - downloads added from the site grabber, grouped by project.
  Queues - lists of downloads you can start and stop together. Right-click a queue to rename or delete it.

THE LIST
  Q is the position in the queue. Click a column title to sort. Double-click a finished file to open it.
  Right-click a download for Open, Resume, Stop, Delete, Move to category/queue, Redownload and Properties.

QUEUES AND THE SCHEDULER
  "Download Later" puts a download in its queue without starting it. Start queue / Stop queue act on the queue
  selected in the left pane (the main queue by default). Downloads > Scheduler restricts downloading to a time window.

SPEED
  Downloads > Speed limiter caps the total speed. View > Segment map shows which parts of the selected download each connection has filled.

EXTRAS
  Antivirus: finished files are checked by Windows Defender or ClamAV if one is installed (AeroGrab has no engine of its own); the
  verdict is in the Download complete window. File > Scan for viruses checks a file again. Options > Extras.
  Resolve link... (Add dialog) finds the real file behind a short link, a redirect or a download page. It reports login and payment
  walls instead of trying to get around them.
  Tasks > Clipboard history keeps the links you copy (turn it on first). View > Floating widget shows a small speed meter.
  Right-click the toolbar, or View > Customize toolbar, to choose and order its buttons. Options > Appearance has skins.""")

    def shortcuts_dialog(self):
        self.text_dialog("Keyboard shortcuts", """Ctrl+N        Add new download
Ctrl+R        Resume the selected downloads
Ctrl+S        Stop the selected downloads
Delete        Delete the selected downloads
Enter         Open a finished file (or show properties)
Alt+Enter     Properties
F2            Move/Rename a finished file
F5            Refresh
Ctrl+A        Select all downloads
Ctrl+C        Copy the address of the selected downloads""", width=60, height=12)

    def about_dialog(self):
        """Branded About window: logo, version, what AeroGrab is, the runtime it runs on, and the licences."""
        px = self.px
        win = tk.Toplevel(self.root)
        win.title(f"About {APP_NAME}")
        win.resizable(False, False)
        win.transient(self.root)
        win._logo = tk.PhotoImage(data=BRAND_B64[64])
        body = ttk.Frame(win, padding=(px(32), px(26), px(32), px(14)))
        body.pack(fill="both", expand=True)
        ttk.Label(body, image=win._logo).pack()
        ttk.Label(body, text=APP_NAME, style="Title.TLabel").pack(pady=(px(10), 0))
        ttk.Label(body, text=f"Version {__version__}", style="Muted.TLabel").pack()
        ttk.Label(body, text=APP_TAGLINE, style="Accent.TLabel").pack(pady=(px(2), px(12)))
        ttk.Label(body, justify="center", wraplength=px(380),
                  text="A free, open-source download manager: segmented downloads, queues, categories, video (HLS), browser integration and a system tray icon.\n\n"
                       "MIT License. No ads, no tracking, nothing to buy.").pack()
        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=px(14))
        ttk.Label(body, justify="center", style="Small.TLabel", wraplength=px(380),
                  text=f"Python {platform.python_version()}  \u00b7  Tk {tk.TkVersion}  \u00b7  {platform.system()} {platform.release()}\n"
                       "Icons: Lucide (lucide.dev), ISC License").pack()
        row = ttk.Frame(win, padding=(px(16), px(4), px(16), px(16)))
        row.pack(fill="x")
        ttk.Button(row, text="Close", style="Accent.TButton", command=win.destroy).pack(side="right")
        ttk.Button(row, text="Licence...", command=self.license_dialog).pack(side="right", padx=(0, px(8)))
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Return>", lambda e: win.destroy())
        _center_over(win, self.root)
        win.focus_set()

    def registration_dialog(self):
        self.info("Registration", "AeroGrab is free and open-source software (MIT License).\n\nThere is nothing to register or buy: no serial number, no trial period, "
                                  "no activation and no nag screens. Every feature is always available.\n\nIf you like it, tell a friend or contribute to the project.")

    def license_dialog(self):
        self.text_dialog("License", MIT_TEXT, width=100, height=20)

    # ------------------------------------------------------------------ system tray
    def show_window(self):
        """Restore (from the tray or the taskbar) and focus the main window. Downloads are not touched."""
        r = self.root
        try:
            r.deiconify()
            if r.state() == "iconic":
                r.state("normal")
            r.lift()
            r.attributes("-topmost", True)  # Windows won't always hand focus to a background app: a brief topmost flip brings it forward
            r.after(300, lambda: r.winfo_exists() and r.attributes("-topmost", False))
            r.focus_force()
        except tk.TclError:
            return
        if os.name == "nt":
            try:
                import ctypes
                u = ctypes.windll.user32
                u.GetParent.restype, u.GetParent.argtypes = ctypes.c_void_p, [ctypes.c_void_p]
                u.SetForegroundWindow.argtypes = [ctypes.c_void_p]
                u.SetForegroundWindow(u.GetParent(r.winfo_id()) or r.winfo_id())
            except Exception:
                pass

    def handle_ipc(self, msg):
        """A later launch of AeroGrab asked this instance to come forward ('ping' = a background start: browser / sign-in)."""
        if msg.get("cmd") == "show":
            self.show_window()

    def set_tray(self, on):
        """Start or stop the tray icon. Returns an error message ('' if all is well)."""
        if on and not self.tray:
            t = Tray(base64.b64decode(ICON_B64), lambda: self.mgr.settings["limit_kb"])
            if t.available:
                t.start()
            if not t.available:
                return t.error
            self.tray = t
        elif not on and self.tray:
            self.tray.stop()
            self.tray = None
            self.show_window()
        return ""

    def handle_cmd(self, cmd):
        if cmd == "show":
            self.show_window()
        elif cmd == "pause_all":
            self.stop_all()
        elif cmd == "resume_all":
            self.resume_items(self.mgr.items)
        elif cmd.startswith("limit:"):
            self.limit_var.set(int(cmd[6:]))
        elif cmd == "folder":
            self.open_path(self.folder.get())
        elif cmd == "quit":
            self.on_close()

    def poll_tray(self):
        if self.single:
            for m in self.single.poll():
                self.handle_ipc(m)
        if self.tray:
            for c in self.tray.poll():
                self.handle_cmd(c)
        self.root.after(150, self.poll_tray)

    def notify_changes(self):
        """Balloon notification when a download finishes or fails while AeroGrab isn't the window in front."""
        for d in self.mgr.items:
            prev, self.seen[id(d)] = self.seen.get(id(d)), d.status
            if prev is None or prev == d.status or not self.tray or not self.mgr.settings.get("notify", True):
                continue
            if self.root.state() in ("normal", "zoomed") and self.root.focus_displayof() is not None:
                continue
            if d.status == "Completed":
                self.tray.notify(f"Finished: {d.label}")
            elif d.status == "Error":
                self.tray.notify(f"Failed: {d.label}\n{d.error[:120]}")

    # ------------------------------------------------------------------ live refresh
    def redraw_segments(self):
        """The segment map under the list: which parts of the selected download each connection has filled."""
        if not self.show_map.get():
            return
        sel = self.selected()
        if len(sel) == 1:
            d = sel[0]
            extra = (f"  \u00b7  {d.segs_done}/{d.total} parts" if isinstance(d, HlsDownload) else f"  \u00b7  {len(d.segs)} segments" if d.segs else "")
            self.gtitle.config(text=f"Segments  \u00b7  {d.label[:60]}{extra}")
            cells = d.segment_map()
        else:
            self.gtitle.config(text="Segments")
            cells = []
        draw_segmap(self.mapcv, cells)

    def update_toolbar(self):
        fl = self.flags()
        for icon, rule in (("resume", "resumable"), ("stop", "active"), ("stopall", "anyactive"), ("delete", "sel"), ("delc", "anydone"), ("scan", "done")):
            if icon in self.tbtn:  # the user may have taken the button off the toolbar
                self.tbtn[icon].state(["!disabled"] if fl[rule] else ["disabled"])

    def tick(self):
        fin = self.mgr.schedule()
        self._guard(self.collect_sounds, fin)
        if fin and self.after_done():
            return
        self._guard(self.follow_system_theme)
        total = sum(d.speed for d in self.mgr.items)
        self.notify_changes()
        self._guard(self.drain_captured)
        self._guard(self.check_completed)
        self._guard(self.watch_scans)
        self._guard(self.report_manual_scans)
        self._guard(self.watch_clipboard)
        self._guard(self.poll_clipboard)
        self._guard(self.poll_update_check)
        self.draw_list()
        self.update_side()
        self.update_toolbar()
        self._guard(self.widget.update)
        self._guard(self.update_progress_windows)
        if self.tray:
            tip = tray_tooltip(self.mgr.items, total)
            if tip != self.last_tip:
                self.last_tip = tip
                self.tray.set_title(tip)
        st = self.mgr.settings
        api_txt = f"Browser API: listening on 127.0.0.1:{self.port}" if self.api_srv else f"Browser API: PORT {self.port} BUSY"
        sch = f" | Schedule {st['start']}-{st['stop']}: {'running' if self.mgr.in_window() else 'waiting'}" if st["sched_on"] else ""
        note = f" | {self.note[0]}" if time.time() < self.note[1] else ""
        self.status.config(text=f"{len(self.mgr.items)} downloads   \u00b7   {human(total)}/s   \u00b7   {api_txt}{sch.replace(' | ', '   \u00b7   ')}   \u00b7   Saving to: {self.folder.get()}{note.replace(' | ', '   \u00b7   ')}")
        self.redraw_segments()
        if int(time.time()) % 3 == 0:
            self.mgr.save()
        self.root.after(500, self.tick)

    # ------------------------------------------------------------------ toolbar: layout, style, customizing
    STYLE_LABELS = {"both": "Icons and text", "icons": "Icons only", "text": "Text only"}
    SIZE_LABELS = {"large": "Large icons", "small": "Small icons"}

    TOOL_TIPS = {"add": "Add a new download (Ctrl+N)", "resume": "Resume the selected downloads (Ctrl+R)", "stop": "Stop the selected downloads (Ctrl+S)",
                 "stopall": "Stop every active download", "delete": "Delete the selected downloads (Del)", "delc": "Remove all completed downloads from the list",
                 "options": "Open AeroGrab options", "scheduler": "Choose when downloads are allowed to run", "startq": "Start the queue selected in the left pane",
                 "stopq": "Stop the queue selected in the left pane", "grabber": "Find downloadable files on a web page", "browser": "Connect AeroGrab to your web browser",
                 "scan": "Scan the selected finished files for viruses", "clip": "Links you copied (Clipboard history)", "widget": "Show or hide the floating speed meter"}

    def rebuild_toolbar(self):
        """(Re)draw the toolbar from the settings: which buttons, in what order, icons and/or text, large or small. Also called after a theme change (icons are re-tinted)."""
        st, px = self.mgr.settings, self.px
        for w in self.toolbar_inner.winfo_children():
            w.destroy()
        self.tbtn = {}
        style = st.get("toolbar_style") if st.get("toolbar_style") in TOOLBAR_STYLES else "both"
        if style == "both" and self._tb_compact:   # not enough width for the labels (small screen or high DPI scaling): icons only, tooltips explain them
            style = "icons"
        size = st.get("toolbar_size") if st.get("toolbar_size") in TOOLBAR_SIZES else "large"
        isz, dim = (24 if size == "large" else 18), self.theme.p["disabled"]
        for bid in toolbar_layout(st.get("toolbar_items"), DEFAULT_TOOLBAR, TOOLBAR_ACTIONS):
            if bid == "|":
                ttk.Separator(self.toolbar_inner, orient="vertical").pack(side="left", fill="y", padx=px(6), pady=px(8))
                continue
            icon, label, meth = TOOLBAR_ACTIONS[bid]
            pics = (self.icon(icon, isz), "disabled", self.icon(icon, isz, color=dim))
            if style == "text":
                kw = {"text": label}
            elif style == "icons":
                kw = {"image": pics}
            else:
                kw = {"text": label, "image": pics, "compound": "top" if size == "large" else "left"}
            b = ttk.Button(self.toolbar_inner, style="Tool.TButton", command=getattr(self, meth), **kw)
            b.pack(side="left", padx=1)
            b.bind("<Button-3>", self._toolbar_menu)
            b.bind("<Control-Button-1>", self._toolbar_menu)
            Tip(b, self.TOOL_TIPS.get(bid, label))
            self.tbtn[bid] = b
        for w in (self.toolbar, self.toolbar_inner):
            for ev in ("<Button-3>", "<Control-Button-1>"):
                w.bind(ev, self._toolbar_menu)
        if style == "both" and not self._tb_compact:
            self.toolbar_inner.update_idletasks()
            self._tb_full_w = self.toolbar_inner.winfo_reqwidth()   # what the labelled toolbar needs, to know when it fits again
        if hasattr(self, "tree"):
            self.update_toolbar()

    def _fit_toolbar(self):
        if self.mgr.settings.get("toolbar_style") not in (None, "both"):
            return
        compact = self.root.winfo_width() < self._tb_full_w + self.px(24)
        if compact != self._tb_compact and self._tb_full_w > 1:
            self._tb_compact = compact
            self.rebuild_toolbar()

    def _toolbar_menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        cur = self.mgr.settings.get("toolbar_style", "both")
        for key in TOOLBAR_STYLES:
            m.add_command(label=self.STYLE_LABELS[key] + ("   \u2713" if cur == key else ""), command=lambda k=key: self.set_toolbar(style=k))
        m.add_separator()
        m.add_command(label="Customize toolbar...", command=self.customize_toolbar)
        self._popup(m, e)

    def set_toolbar(self, items=False, style=None, size=None):
        st = self.mgr.settings
        if items is not False:
            st["toolbar_items"] = items
        if style:
            st["toolbar_style"] = style
        if size:
            st["toolbar_size"] = size
        self.mgr.save_settings()
        self.rebuild_toolbar()

    def customize_toolbar(self):
        st = self.mgr.settings
        win = tk.Toplevel(self.root)
        win.title("Customize toolbar")
        win.transient(self.root)
        items = toolbar_layout(st.get("toolbar_items"), DEFAULT_TOOLBAR, TOOLBAR_ACTIONS)
        avail = []
        name = lambda b: "-------- separator --------" if b == "|" else TOOLBAR_ACTIONS[b][1]
        frm = ttk.Frame(win, padding=12)
        frm.pack()
        ttk.Label(frm, text="On the toolbar (left to right):").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Available:").grid(row=0, column=2, sticky="w")
        lb_cur = tk.Listbox(frm, height=15, width=26, exportselection=False)
        lb_cur.grid(row=1, column=0)
        lb_av = tk.Listbox(frm, height=15, width=26, exportselection=False)
        lb_av.grid(row=1, column=2)
        mid = ttk.Frame(frm)
        mid.grid(row=1, column=1, padx=10)

        def refill(select=None):
            lb_cur.delete(0, "end")
            for b in items:
                lb_cur.insert("end", name(b))
            avail[:] = [b for b in TOOLBAR_ACTIONS if b not in items] + ["|"]
            lb_av.delete(0, "end")
            for b in avail:
                lb_av.insert("end", name(b))
            if select is not None and items:
                lb_cur.selection_set(max(0, min(select, len(items) - 1)))
            lb_av.selection_set(0)

        def add():
            sel, at = lb_av.curselection(), lb_cur.curselection()
            if sel:
                pos = at[0] + 1 if at else len(items)
                items.insert(pos, avail[sel[0]])
                refill(pos)

        def remove():
            sel = lb_cur.curselection()
            if sel:
                items.pop(sel[0])
                refill(sel[0])

        def move(delta):
            sel = lb_cur.curselection()
            if sel and 0 <= sel[0] + delta < len(items):
                i, j = sel[0], sel[0] + delta
                items[i], items[j] = items[j], items[i]
                refill(j)
        for text, fn in (("Add  >>", add), ("<<  Remove", remove), ("Move up", lambda: move(-1)), ("Move down", lambda: move(1))):
            ttk.Button(mid, text=text, command=fn, width=11).pack(pady=3)
        style = tk.StringVar(value=self.STYLE_LABELS.get(st.get("toolbar_style"), self.STYLE_LABELS["both"]))
        size = tk.StringVar(value=self.SIZE_LABELS.get(st.get("toolbar_size"), self.SIZE_LABELS["large"]))
        opt = ttk.Frame(win, padding=(12, 0))
        opt.pack(fill="x")
        ttk.Label(opt, text="Buttons show:").pack(side="left")
        ttk.Combobox(opt, textvariable=style, state="readonly", width=16, values=list(self.STYLE_LABELS.values())).pack(side="left", padx=(4, 14))
        ttk.Combobox(opt, textvariable=size, state="readonly", width=14, values=list(self.SIZE_LABELS.values())).pack(side="left")

        def reset():
            items[:] = DEFAULT_TOOLBAR
            style.set(self.STYLE_LABELS["both"])
            size.set(self.SIZE_LABELS["large"])
            refill(0)

        def ok():
            back = lambda labels, v: next(k for k, t in labels.items() if t == v.get())
            final = toolbar_layout(items, DEFAULT_TOOLBAR, TOOLBAR_ACTIONS)
            self.set_toolbar(items=None if final == DEFAULT_TOOLBAR else final, style=back(self.STYLE_LABELS, style), size=back(self.SIZE_LABELS, size))
            win.destroy()
        row = ttk.Frame(win)
        row.pack(pady=12)
        ttk.Button(row, text="OK", style="Accent.TButton", command=ok).pack(side="left", padx=6)
        ttk.Button(row, text="Reset to default", command=reset).pack(side="left", padx=6)
        ttk.Button(row, text="Cancel", command=win.destroy).pack(side="left", padx=6)
        refill(0)

    # ------------------------------------------------------------------ floating widget
    def toggle_widget(self, on=None):
        on = (not self.widget.shown) if on is None else bool(on)
        self.show_widget.set(on)
        self.mgr.settings["widget_on"] = on
        self.mgr.save_settings()
        self.widget.show() if on else self.widget.hide()

    # ------------------------------------------------------------------ clipboard history
    def watch_clipboard(self):
        """While 'keep a history of copied links' is on, notice new clipboard text about once a second. Only the web / FTP addresses in it are kept."""
        if not self.mgr.settings.get("clip_watch"):
            return
        now = time.time()
        if now - self._clip_check < 1.0:
            return
        self._clip_check = now
        try:
            text = self.root.clipboard_get()
        except tk.TclError:  # empty, or not text
            text = ""
        if self._clip_last is None:  # just switched on: what is already on the clipboard was not copied "now"
            self._clip_last = text
            return
        if text == self._clip_last:
            return
        self._clip_last = text
        new = self.clips.add_text(text)
        if new:
            self.flash(f"Saved {len(new)} copied link{'s' if len(new) > 1 else ''} to Tasks > Clipboard history")
            self._fill_clip_list()

    def download_links(self, urls, later=False):
        """Add links (from the clipboard history ...) to the queue shown on the left, with redirect wrappers peeled off if that option is on."""
        added = []
        for u in urls:
            if self.mgr.settings.get("smart_unwrap", True):
                u = unwrap_url(u)[0]
            try:
                added.append(self.mgr.add(u, self.folder.get(), self.conns.get(), queue=self.cur_queue(), later=later))
            except ValueError as e:
                messagebox.showerror("AeroGrab", str(e), parent=self.root)
        self.after_change()
        if not later:
            for d in added[:3]:
                self.progress_window(d)
        return added

    def _fill_clip_list(self):
        tv = getattr(self, "_clip_tree", None)
        try:
            if tv is None or not tv.winfo_exists():
                return
            tv.delete(*tv.get_children())
            for i, x in enumerate(self.clips.items):
                tv.insert("", "end", iid=str(i), values=(x["url"], fmt_when(x["t"]) if x["t"] else ""))
        except tk.TclError:
            pass

    def clipboard_dialog(self):
        st = self.mgr.settings
        old = getattr(self, "_clip_win", None)
        try:
            if old is not None and old.winfo_exists():
                self._front(old)
                return
        except tk.TclError:
            pass
        win = self._clip_win = tk.Toplevel(self.root)
        win.title("Clipboard history")
        win.transient(self.root)
        win.geometry("760x420")
        watch = tk.BooleanVar(value=bool(st.get("clip_watch")))

        def set_watch():
            st["clip_watch"] = watch.get()
            self._clip_last = None
            self.mgr.save_settings()
        ttk.Checkbutton(win, text="Keep a history of links I copy (only web and FTP addresses are kept - never other clipboard text)", variable=watch, command=set_watch).pack(anchor="w", padx=12, pady=(10, 4))
        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=12)
        tv = self._clip_tree = ttk.Treeview(box, columns=("url", "when"), show="headings", selectmode="extended")
        tv.heading("url", text="Link")
        tv.heading("when", text="Copied")
        tv.column("url", width=520)
        tv.column("when", width=170)
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)

        def chosen():
            rows = tv.selection() or tv.get_children()  # nothing selected = all of them
            return [self.clips.items[int(i)]["url"] for i in rows if int(i) < len(self.clips.items)]

        def need(urls):
            if not urls:
                messagebox.showinfo("Clipboard history", "There are no links yet. Turn on the check box above, then copy a link.", parent=win)
            return bool(urls)

        def download(later=False):
            urls = chosen()
            if need(urls):
                self.download_links(urls, later)
                if later:
                    self.flash(f"{len(urls)} link(s) added; start them when you like")

        def copy():
            urls = chosen()
            if need(urls):
                self.root.clipboard_clear()
                self.root.clipboard_append("\n".join(urls))
                self._clip_last = "\n".join(urls)  # our own copy is not a new entry

        def remove():
            sel = [self.clips.items[int(i)]["url"] for i in tv.selection() if int(i) < len(self.clips.items)]
            if sel:
                self.clips.remove(sel)
                self._fill_clip_list()

        def clear():
            if self.clips.items and messagebox.askyesno("Clipboard history", "Delete the whole history?", parent=win):
                self.clips.clear()
                self._fill_clip_list()
        tv.bind("<Double-1>", lambda e: download() if tv.identify_row(e.y) else None)
        row = ttk.Frame(win)
        row.pack(pady=10)
        for text, fn in (("Download", download), ("Download later", lambda: download(True)), ("Copy", copy), ("Remove", remove), ("Clear all", clear), ("Close", win.destroy)):
            ttk.Button(row, text=text, command=fn).pack(side="left", padx=4)
        self._fill_clip_list()

    # ------------------------------------------------------------------ antivirus
    def scan_selected(self):
        """File > Scan for viruses: run the installed antivirus over the selected finished files and report."""
        st = self.mgr.settings
        ds = [d for d in self.selected() if d.status == "Completed" and d.path and os.path.exists(d.path)]
        if not ds:
            return self.info("Scan for viruses", "Select a finished download first.")
        if not find_av(st.get("av_engine", "auto")):
            return self.info("Scan for viruses", "No antivirus was found.\n\nAeroGrab has no scanner of its own: it asks Windows Defender (MpCmdRun.exe) or ClamAV (clamscan) "
                             "when one is installed. Install one of them, or change the scanner under Options > Extras.")
        for d in ds:
            d._threat_told = True  # this scan reports itself below
            d.scan_async(st.get("av_engine", "auto"), force=True)
            self.scan_watch.append(d)
        self.flash(f"Scanning {len(ds)} file(s)...")

    def report_manual_scans(self):
        if self.scan_watch and not any(d._scanning for d in self.scan_watch):
            done, self.scan_watch = self.scan_watch, []
            text = "\n\n".join(f"{d.label}\n{d.scan_info}" for d in done)
            (messagebox.showwarning if any(d.scan == "infected" for d in done) else messagebox.showinfo)("Scan for viruses", text, parent=self.root)

    def watch_scans(self):
        """A threat found after the Download complete window was already dismissed (slow scan) must still be seen."""
        for d in self.mgr.items:
            if d.scan == "infected" and not getattr(d, "_threat_told", False):
                d._threat_told = True
                self.flash(f"THREAT FOUND in {d.label}", 20)
                if self.tray and self.mgr.settings.get("notify", True):
                    self.tray.notify(f"Antivirus: threat found in {d.label}")
                if not getattr(d, "_scan_shown", False):
                    messagebox.showwarning("AeroGrab - threat found", f"{d.label}\n\n{d.scan_info}\n\nThe file was kept where it is; AeroGrab doesn't delete or open it.", parent=self.root)

    # ------------------------------------------------------------------ smart links (Add dialog)
    def resolve_in_dialog(self, win, txt, note):
        """Work out the real file behind each pasted link (redirects, shorteners, 'your download starts soon' pages). Runs in the background."""
        lines = [x.strip() for x in txt.get("1.0", "end").splitlines() if x.strip()]
        urls = [x for x in lines if x.lower().startswith(("http://", "https://"))][:20]
        if not urls:
            note.config(text="Paste an http:// or https:// address first.")
            return
        note.config(text=f"Looking at {len(urls)} link(s)...")
        out, results = queue.Queue(), []

        def work():
            for u in urls:
                try:
                    out.put((u, resolve_link(u)))
                except Exception as e:
                    out.put((u, {"url": u, "state": "failed", "note": str(e), "steps": [], "candidates": []}))
            out.put(None)
        threading.Thread(target=work, daemon=True).start()

        def finish():
            notes, mapping = [], {}
            for u, r in results:
                short = u if len(u) < 56 else u[:53] + "..."
                if r["state"] == "choose":
                    pick = self.choose_link(win, u, r["candidates"])
                    if pick:
                        mapping[u] = pick
                    notes.append(f"{short}: " + ("picked the link you chose" if pick else "left as it was"))
                elif r["state"] in ("direct", "resolved"):
                    if r["url"] != u:
                        mapping[u] = r["url"]
                    notes.append(f"{short}: {r['note'] or 'ok'}")
                else:
                    notes.append(f"{short}: {r['note'] or r['state']}")
            txt.delete("1.0", "end")
            txt.insert("1.0", "\n".join(mapping.get(x, x) for x in lines))
            note.config(text="\n".join(notes))

        def poll():
            if not win.winfo_exists():
                return
            try:
                while True:
                    item = out.get_nowait()
                    if item is None:
                        return finish()
                    results.append(item)
            except queue.Empty:
                win.after(150, poll)
        poll()

    def choose_link(self, parent, source, cands):
        dlg = tk.Toplevel(parent)
        dlg.title("Which link is the file?")
        dlg.transient(parent)
        ttk.Label(dlg, text=f"{source}\nhas several links that could be the file:", justify="left", wraplength=640).pack(anchor="w", padx=12, pady=(12, 4))
        lb = tk.Listbox(dlg, width=96, height=min(8, len(cands)), exportselection=False)
        lb.pack(padx=12)
        for c in cands:
            lb.insert("end", f"{(c['text'] or '(no text)')[:36]:<38}{c['url']}")
        lb.selection_set(0)
        result = [None]

        def ok():
            sel = lb.curselection()
            result[0] = cands[sel[0]]["url"] if sel else None
            dlg.destroy()
        lb.bind("<Double-1>", lambda e: ok())
        row = ttk.Frame(dlg)
        row.pack(pady=10)
        ttk.Button(row, text="Use this link", command=ok).pack(side="left", padx=6)
        ttk.Button(row, text="Keep the original", command=dlg.destroy).pack(side="left", padx=6)
        self._front(dlg)
        dlg.grab_set()
        dlg.wait_window()
        return result[0]

    # ------------------------------------------------------------------ updates (GitHub Releases)
    def start_update_check(self, manual=False):
        """Asks GitHub in the background. The answer is picked up by poll_update_check() on the GUI thread."""
        if self._upd_busy:
            return
        self._upd_busy = True

        def run():
            try:
                res = ("ok", check_for_update())
            except Exception as e:
                res = ("error", str(e) or e.__class__.__name__)
            self.update_q.put((manual, res))
        threading.Thread(target=run, daemon=True).start()

    def poll_update_check(self):
        if self._upd_pending and self.update_info and self.root.state() == "normal" and not (self._upd_win and self._upd_win.winfo_exists()):
            self._upd_pending = False  # an update was found while AeroGrab sat in the tray: offer it as soon as the window is opened
            self.update_dialog(self.update_info)
        while True:
            try:
                manual, (state, val) = self.update_q.get_nowait()
            except queue.Empty:
                return
            self._upd_busy = False
            if state == "error":
                if manual:
                    messagebox.showerror("Check for updates", f"Could not check for updates:\n{val}", parent=self.root)
            elif val["newer"]:
                self.update_info = val
                if not manual and self.root.state() in ("withdrawn", "iconic"):
                    self._upd_pending = True
                    if self.tray:
                        self.tray.notify(f"AeroGrab {val['version']} is available. Open the window to update.")
                else:
                    self.update_dialog(val)
            elif manual:
                self.info("Check for updates", f"You have the latest version (AeroGrab {__version__}).")

    def update_dialog(self, info):
        """'AeroGrab x.y.z is available': release notes, then Update now / Later. Update now downloads the right file for this copy
        (portable .exe or installer), shows the progress, and hands over to a helper script that restarts AeroGrab when it is done."""
        if self._upd_win and self._upd_win.winfo_exists():
            return self._front(self._upd_win)
        kind, asset = info["kind"], info["asset"]
        auto = kind in ("portable", "installed") and bool(asset)
        win = self._upd_win = tk.Toplevel(self.root)
        win.title("Update available")
        win.transient(self.root)
        win.resizable(True, True)
        ttk.Label(win, text=f"AeroGrab {info['version']} is available", font="AeroHeading").pack(anchor="w", padx=14, pady=(14, 0))
        how = ({"portable": "The portable version will be downloaded and replaced in place; AeroGrab then restarts by itself.",
                "installed": "The installer will be downloaded and run for you; AeroGrab then restarts by itself."}[kind] if auto
               else "This copy of AeroGrab can't update itself, so the download page will open in your browser.")
        ttk.Label(win, text=f"You are using version {__version__}. {how}", wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(2, 8))
        box = ttk.Frame(win)
        box.pack(fill="both", expand=True, padx=14)
        t = tk.Text(box, width=70, height=12, wrap="word", padx=8, pady=6)
        sb = ttk.Scrollbar(box, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.insert("1.0", info["notes"])
        t.config(state="disabled")
        busy = sum(1 for d in self.mgr.items if d.status in ACTIVE)
        if busy and auto:
            ttk.Label(win, text=f"{busy} active download{'s' if busy != 1 else ''} will be paused now and can be resumed after the restart.",
                      wraplength=520, justify="left").pack(anchor="w", padx=14, pady=(8, 0))
        status = ttk.Label(win, text="", wraplength=520, justify="left")
        bar = ttk.Progressbar(win, mode="determinate", maximum=100)
        row = ttk.Frame(win)
        row.pack(side="bottom", pady=12)
        now = ttk.Button(row, text="Update now", style="Accent.TButton" if auto else "Open download page")
        later = ttk.Button(row, text="Later")
        now.pack(side="left", padx=6)
        later.pack(side="left", padx=6)
        run = {"stop": threading.Event(), "busy": False}

        def close():
            run["stop"].set()
            if win.winfo_exists():
                win.destroy()

        def fail(msg):
            run["busy"] = False
            bar.pack_forget()
            status.config(text=msg)
            status.pack(anchor="w", padx=14, pady=(8, 0))
            now.state(["!disabled"])
            later.config(text="Later", command=close)

        def go():
            if not auto:
                import webbrowser
                webbrowser.open(info["page"])
                return close()
            try:
                dest = stage_path(kind, asset)
            except Exception as e:
                return fail(str(e))
            run["stop"].clear()
            run["busy"] = True
            st = {"done": 0, "total": int(asset.get("size") or 0), "err": "", "fin": False}
            now.state(["disabled"])
            later.config(text="Cancel")
            status.config(text="Downloading...")
            status.pack(anchor="w", padx=14, pady=(8, 0))
            bar.pack(fill="x", padx=14, pady=(4, 0))

            def work():
                try:
                    st["path"] = download_update(asset, dest, progress=lambda d, tot: st.update(done=d, total=tot or st["total"]), stop=run["stop"])
                except Exception as e:
                    st["err"] = str(e)
                st["fin"] = True
            threading.Thread(target=work, daemon=True).start()

            def poll():
                if not win.winfo_exists():
                    return
                if not st["fin"]:
                    pct = st["done"] * 100 / st["total"] if st["total"] else 0
                    bar.config(value=pct)
                    status.config(text=f"Downloading...  {human(st['done'])}" + (f" of {human(st['total'])}  ({pct:.0f}%)" if st["total"] else ""))
                    return win.after(120, poll)
                if st["err"]:
                    return fail("" if st["err"] == "Cancelled." else st["err"])
                bar.config(value=100)
                status.config(text="Installing the update. AeroGrab will restart in a moment...")
                try:
                    apply_update(kind, st["path"])
                except Exception as e:
                    return fail(f"Could not start the update: {e}")
                win.after(400, self.on_close)  # pauses the downloads, saves, quits; the helper script takes over from here
            poll()

        now.config(command=go)
        later.config(command=close)
        win.protocol("WM_DELETE_WINDOW", close)
        self._front(win)

    # ------------------------------------------------------------------ closing and starting
    def on_close(self):  # really quit
        self.mgr.shutdown()
        if self.single:
            self.single.close()  # give the instance lock + pipe back before the window goes
        self.root.destroy()

    def request_close(self):  # the window's X button: hide to the tray if there is one
        if self.tray and self.mgr.settings.get("close_to_tray", True):
            self.root.withdraw()
            if not self.hint_shown:
                self.hint_shown = True
                self.tray.notify("AeroGrab is still running in the tray. Right-click the icon to quit.")
        else:
            self.on_close()

    def run(self):
        if self.mgr.settings.get("native_register", True):
            self.register_browsers(silent=True)  # keeps the registration pointing at this copy of AeroGrab, even after it was moved
        if self.mgr.settings.get("tray", True):
            self.set_tray(True)  # if it can't start, Options explains why
        self.poll_tray()
        if self.mgr.settings.get("widget_on"):
            self.widget.show()
        self.tick()
        self._capture_pump()
        threading.Thread(target=warm_up, daemon=True).start()
        if self.mgr.settings.get("check_updates", True) and not os.environ.get("AEROGRAB_NO_UPDATE_CHECK"):
            self.root.after(4000, self.start_update_check)  # a few seconds after start-up, in the background; silent when there is nothing new or no internet
        if self.minimized or self.mgr.settings.get("start_minimized"):
            self.root.withdraw() if self.tray else self.root.iconify()
        self.root.mainloop()
        if self.tray:
            self.tray.stop()
        if self.single:
            self.single.close()


def run_gui(port=API_PORT, minimized=False, single=None):
    App(port, minimized, single).run()


# ============================== CLI ==============================
def run_cli(args):
    """Returns the exit code: 0 if every download finished (and matched its checksum), 1 if not, 2 for a bad option."""
    mgr = Manager(args.max_active, persist=False)
    mgr.settings["av_scan"] = False  # the CLI scans only with --scan, after the download
    mgr.set_limit_kb(args.limit)
    mgr.settings["folder"], mgr.settings["auto_sort"] = os.path.expanduser(args.output), args.sort
    mgr.settings["quality"] = args.quality
    checksum = getattr(args, "checksum", "") or ""
    if checksum and len(args.urls) != 1:
        print("--checksum needs exactly one address")
        return 2
    try:
        if getattr(args, "proxy", None):
            mgr.settings.update(parse_proxy(args.proxy))
            mgr.apply_network()
        ds = [mgr.add(u, os.path.expanduser(args.output), args.connections, **({"checksum": checksum} if checksum else {})) for u in args.urls]
    except ValueError as e:
        print(f"AeroGrab: {e}")
        return 2

    def pending(d):  # not finished, or finished but its checksum hasn't been compared yet, or failed but about to be retried
        return d.status not in ("Completed", "Error") or (d.status == "Completed" and d.checksum and not d.verified) or mgr.will_retry(d)
    try:
        while any(pending(d) for d in ds):
            mgr.schedule()
            line = " | ".join(f"{(d.name or '...')[:25]} {d.percent:5.1f}% {human(d.speed)}/s" for d in ds)
            print("\r" + line[:110].ljust(110), end="", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        for d in ds:
            d.pause()
        print("\nInterrupted.")
        return 130
    print()
    bad = 0
    for d in ds:
        print(f"{d.status}: {d.path or d.url} {d.error}")
        if d.checksum:
            print(f"  {d.checksum.split(':')[0].upper()}: " + {"ok": "matches", "bad": f"DOES NOT MATCH (the file's is {d.actual_hash})", "missing": "file not found"}.get(d.verified, "not checked"))
        bad += d.status != "Completed" or d.verified in ("bad", "missing")
        if getattr(args, "scan", False) and d.status == "Completed":
            res = scan_file(d.path)
            print("  " + av_summary(res))
            bad += res["state"] == "infected"
    return 1 if bad else 0


if __name__ == "__main__":
    if is_native_host_launch(sys.argv):  # started by a browser: speak native messaging, nothing else
        sys.exit(NativeHost().serve(sys.argv[1:]))
    p = argparse.ArgumentParser(description="AeroGrab download manager")
    p.add_argument("--register-browsers", action="store_true", help="register the browser extension's native-messaging host (Windows Registry / browser folders), then exit")
    p.add_argument("--unregister-browsers", action="store_true", help="remove that registration, then exit")
    p.add_argument("--extension-id", action="append", default=[], metavar="ID", help="also trust this extension ID (e.g. from the Chrome Web Store); saved to settings")
    p.add_argument("--minimized", action="store_true", help="start minimized (to the system tray if available)")
    p.add_argument("--version", action="version", version=f"AeroGrab {__version__}")
    p.add_argument("urls", nargs="*", help="URLs to download (omit to open the GUI)")
    p.add_argument("-n", "--connections", type=int, default=8)
    p.add_argument("-o", "--output", default="~/Downloads")
    p.add_argument("-m", "--max-active", type=int, default=3)
    p.add_argument("--sort", action="store_true", help="CLI: sort files into category sub-folders (Video, Documents, ...)")
    p.add_argument("-l", "--limit", type=int, default=0, help="speed limit in KB/s (0 = unlimited)")
    p.add_argument("-q", "--quality", type=int, default=0, help="max video height for HLS streams (0 = best)")
    p.add_argument("-p", "--port", type=int, default=API_PORT, help="browser-extension API port (GUI mode)")
    p.add_argument("--checksum", default="", metavar="HASH", help="CLI: expected MD5 / SHA-1 / SHA-256 / SHA-512 of the (single) file, e.g. sha256:ab12... - exit code 1 if it doesn't match")
    p.add_argument("--scan", action="store_true", help="CLI: scan each finished file with Windows Defender or ClamAV if one is installed (exit code 1 if a threat is found)")
    p.add_argument("--proxy", default="", metavar="URL", help="CLI: use this proxy, e.g. http://user:pw@host:3128 or socks5://host:1080")
    a = p.parse_args()
    if a.register_browsers or a.unregister_browsers or a.extension_id:
        mg = Manager(persist=True)
        st = mg.settings
        if a.extension_id:
            st["extension_ids"] = sorted(set(extension_ids(list(st.get("extension_ids", [])) + a.extension_id)) - set(DEFAULT_EXTENSION_IDS))
            mg.save_settings()
        ni = NativeIntegration(st.get("extension_ids", []))
        if a.unregister_browsers:
            ni.unregister()
            print("Removed AeroGrab's browser registration.")
        else:
            for r in ni.register():
                print(f"{r['label']:16} {'registered' if r['registered'] else 'skipped'}  {r['detail']}")
        sys.exit(0)
    if a.urls:
        sys.exit(run_cli(a) or 0)
    inst = claim_or_forward(a.minimized)  # one GUI per user: a second launch hands over to the running one and ends here
    if inst is None:
        sys.exit(0)
    try:
        run_gui(a.port, a.minimized, inst)
    finally:
        inst.close()
        _t = threading.Timer(8.0, lambda: os._exit(0))
        _t.daemon = True
        _t.start()  # Exit must end the process even if a stray non-daemon thread lingers
