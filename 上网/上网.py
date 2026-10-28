# -*- coding: utf-8 -*-
"""
深职大有线网络认证（深澜 SRUN srun_bx1）自动登录
==================================================

功能：读取同目录 账号.txt（第 1 行账号、第 2 行密码），自动完成校园网认证登录，
      无需每次手动输入账号密码、勾选协议。

用法：
    上网.py                     正常登录
    上网.py --check             只检测连通性/登录状态，不提交
    上网.py --wait 120          未联网时最多等 120 秒（默认 0 秒，即只试一次）
    上网.py --interval 5        重试间隔秒数（默认 5 秒）

    退出码：0 成功/已在线  1 配置缺失  2 网络不可达  3 登录失败

依赖：仅 Python 标准库（hashlib / hmac / json / urllib / base64 / socket）。
账号密码明文存放在 账号.txt，请勿公开账号文件或包含个人信息的日志。

关于“在线判断”（2026-10 修正）：
    旧版用 /cgi-bin/get_challenge 返回的 online_ip 判断在线，但这个字段只是
    “本机 IP”，与是否已登录无关（换任意用户名请求它照样返回），所以永远误报
    “已在线”，程序也就从不真正发起登录。
    现在改为：
      1) 真正访问外网 204 探测地址，能通才算在线；
      2) 用 /cgi-bin/rad_user_info 查询本机 IP 的真实会话（含 user_name）；
      3) 若门户显示在线但外网不通（会话僵死），自动注销后重新认证。
"""

import os
import sys
import re
import json
import time
import base64
import hashlib
import hmac as hmac_mod
import socket
import urllib.request
import urllib.error
import urllib.parse

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
PORTAL = "https://renzheng.szpu.edu.cn"          # 认证门户
PC_PAGE = PORTAL + "/srun_portal_pc?ac_id=1&theme=pro"
CHALLENGE_API = PORTAL + "/cgi-bin/get_challenge"  # 取 challenge(token)
AUTH_API = PORTAL + "/cgi-bin/srun_portal"          # 认证登录 / 注销
RAD_USER_INFO = PORTAL + "/cgi-bin/rad_user_info"   # 查询本机在线会话

ACID = "1"            # 认证区域，取自门户 CONFIG
N = 200               # 随机参数 n
TYPE = 1              # 认证类型
ENC_VER = "srun_bx1"  # 加密版本

# 外网连通性探测：只认 HTTP 204。被门户劫持时通常返回 200/302，不会被误判为在线。
PROBE_URLS = (
    "http://connect.rom.miui.com/generate_204",
    "http://connectivitycheck.platform.hicloud.com/generate_204",
    "http://www.gstatic.com/generate_204",
)
PROBE_HTTPS_URL = "https://www.baidu.com"   # 204 全部失败时的备选（须真正访问到外网）
PROBE_TIMEOUT = 4      # 单个探测地址超时（秒）
VERIFY_SECONDS = 15    # 登录后等待网络生效的最长时间（秒）

# 自定义 Base64 字母表（来自 Portal.js _encodeUserInfo）
BASE64_ALPHA = "LVoJPiCN2R8G90yg+hmFHuacZ1OWMnrsSTXkYpUq/3dlbfKwv6xztjI7DeBE45QA"
STD_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

# PyInstaller 单文件模式下，配置放在 exe 旁，而不是临时解包目录中。
HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
ACCOUNT_FILE = os.path.join(HERE, "账号.txt")
LOG_FILE = os.path.join(HERE, "上网日志.txt")

ERROR_TIPS = {
    "sign_error": "（签名校验失败；通常是账号/密码含特殊字符，或门户算法有变更）",
    "login_error": "（账号或密码错误，或认证被拒绝）",
    "chksum_error": "（校验失败）",
    "auth_error": "（认证被拒绝）",
    "user_must_modify_password": "（需要先登录 https://i.szpu.edu.cn 修改密码）",
    "account_locked": "（账号被锁定，请稍后再试）",
}


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
def log(msg):
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        print(line)
    except Exception:
        pass  # 无控制台运行时忽略打印错误
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def log_divider():
    log("=" * 50)


# ---------------------------------------------------------------------------
# 配置读取：账号.txt（第 1 行账号、第 2 行密码；# 注释、空行忽略、行首尾空格去除）
# ---------------------------------------------------------------------------
def read_account():
    if not os.path.exists(ACCOUNT_FILE):
        log("未找到账号文件：" + ACCOUNT_FILE)
        log("请新建 账号.txt，第 1 行填账号，第 2 行填密码（UTF-8 保存）。")
        return None, None

    username = None
    password = None
    with open(ACCOUNT_FILE, "r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if username is None:
                username = line
            elif password is None:
                password = line
                break
    if not username or not password:
        log("账号.txt 内容不完整（需第 1 行账号、第 2 行密码）。")
        return None, None
    return username, password


# ---------------------------------------------------------------------------
# HTTP 工具
# ---------------------------------------------------------------------------
def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def jsonp_get(url, params, callback="jsonp", timeout=15):
    """以 JSONP 方式 GET，并解析出回调里的 JSON 对象；失败返回 None。"""
    params = dict(params)
    params["callback"] = callback
    qs = urllib.parse.urlencode(params)
    full = url + ("&" if "?" in url else "?") + qs
    body = http_get(full, timeout).strip()
    # 去掉 JSONP 包装：jsonp({...})  或  jsonp(...); 等
    m = re.match(r'^[\w$.]+\s*\((.*)\)\s*;?\s*$', body, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 也可能是纯 JSON
    try:
        return json.loads(body)
    except Exception:
        return None


def probe_internet(timeout=PROBE_TIMEOUT):
    """真正访问外网 204 接口。返回 (是否可上网, 命中的地址)。"""
    for url in PROBE_URLS:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 204:
                    return True, url
        except Exception:
            continue

    # 备选：HTTPS 访问外网站点。被门户劫持时证书校验会失败，不会误判。
    try:
        req = urllib.request.Request(PROBE_HTTPS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            host = urllib.parse.urlparse(resp.geturl()).netloc.lower()
            if resp.status == 200 and host.endswith("baidu.com"):
                return True, PROBE_HTTPS_URL
    except Exception:
        pass
    return False, None


# ---------------------------------------------------------------------------
# 加密算法（严格对照门户 Portal.js，已用正确签名实测通过）
# ---------------------------------------------------------------------------
def _str_to_words(s, append_len):
    """对应 JS 的 s(a, b)：把字符串按 4 字节一组转 little-endian 32 位字数组。"""
    b = s.encode("utf-8")
    n = len(b)
    padded = b + b"\x00" * ((4 - n % 4) % 4)
    v = [int.from_bytes(padded[i:i + 4], "little") for i in range(0, len(padded), 4)]
    if append_len:
        v.append(n)  # JS: v[v.length] = c（ASCII 下 c == 字节数）
    return v


def _words_to_bytes(v):
    """对应 JS 的 l(a, false)：每个字输出 4 字节（低字节在前）。"""
    return b"".join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in v)


def xxtea_encrypt(s, key):
    """对应 JS encode(str, key)：srun_bx1 的 XXTEA 变体加密。"""
    if s == "":
        return b""
    v = _str_to_words(s, True)      # 附长度
    k = _str_to_words(key, False)   # 不附长度
    if len(k) < 4:
        k = k + [0] * (4 - len(k))

    n = len(v) - 1
    z = v[n]
    y = v[0]
    delta = 0x9E3779B9
    q = 6 + 52 // (n + 1)
    d = 0
    while q > 0:
        q -= 1
        d = (d + delta) & 0xFFFFFFFF
        e = (d >> 2) & 3
        for p in range(n):
            y = v[p + 1]
            m = (z >> 5) ^ ((y << 2) & 0xFFFFFFFF)
            m = (m + (((y >> 3) ^ (z << 4)) ^ (d ^ y))) & 0xFFFFFFFF
            m = (m + (k[(p & 3) ^ e] ^ z)) & 0xFFFFFFFF
            z = v[p] = (v[p] + m) & 0xFFFFFFFF
        y = v[0]
        m = (z >> 5) ^ ((y << 2) & 0xFFFFFFFF)
        m = (m + (((y >> 3) ^ (z << 4)) ^ (d ^ y))) & 0xFFFFFFFF
        m = (m + (k[(n & 3) ^ e] ^ z)) & 0xFFFFFFFF
        z = v[n] = (v[n] + m) & 0xFFFFFFFF
    return _words_to_bytes(v)


def b64_encode(data):
    """标准 Base64（含 '=' 填充），再映射到 srun 自定义字母表。"""
    assert len(set(BASE64_ALPHA)) == 64 and len(BASE64_ALPHA) == 64, "自定义字母表错误"
    std = base64.b64encode(data).decode("ascii")
    trans = str.maketrans(STD_ALPHA, BASE64_ALPHA)
    return std.translate(trans)


def hmd5_of(password, token):
    """hmd5 = HMAC-MD5(key=token, message=password)，小写十六进制。"""
    return hmac_mod.new(token.encode("utf-8"), password.encode("utf-8"),
                        hashlib.md5).hexdigest()


def sha1_hex(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def build_login_params(username, password, ip, token):
    """构造认证参数，返回完整 query 字典。"""
    # info = '{SRBX1}' + base64( xxtea(json) )
    info_obj = {
        "username": username,
        "password": password,
        "ip": ip,
        "acid": ACID,
        "enc_ver": ENC_VER,
    }
    info_json = json.dumps(info_obj, separators=(",", ":"), ensure_ascii=False)
    info = "{SRBX1}" + b64_encode(xxtea_encrypt(info_json, token))

    hmd5 = hmd5_of(password, token)

    # chksum = sha1( token+username+token+hmd5+token+ac_id+token+ip+token+n+token+type+token+info )
    chkstr = (token + username + token + hmd5 + token + ACID + token + ip +
              token + str(N) + token + str(TYPE) + token + info)
    chksum = sha1_hex(chkstr)

    return {
        "action": "login",
        "username": username,
        "password": "{MD5}" + hmd5,
        "chksum": chksum,
        "info": info,
        "ac_id": ACID,
        "ip": ip,
        "n": str(N),
        "type": str(TYPE),
        "os": "Windows",
        "name": "windows",
        "double_stack": "0",
    }


# ---------------------------------------------------------------------------
# 门户状态
# ---------------------------------------------------------------------------
_client_ip = None


def get_client_ip():
    """获取当前客户端 IP：门户 CONFIG → rad_user_info → 本机路由兜底。"""
    global _client_ip
    if _client_ip:
        return _client_ip

    try:
        html = http_get(PC_PAGE)
        m = re.search(r'\bip\s*:\s*"([\d.]+)"', html)
        if m:
            _client_ip = m.group(1)
            return _client_ip
    except Exception as e:
        log("获取门户页面失败：" + str(e))

    res = get_portal_session()
    if res and res.get("client_ip"):
        _client_ip = str(res["client_ip"])
        return _client_ip

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("223.5.5.5", 80))  # 只查路由，不真正发包
            _client_ip = s.getsockname()[0]
        finally:
            s.close()
        return _client_ip
    except Exception:
        return None


def get_portal_session():
    """查询本机 IP 的真实在线会话（rad_user_info）。失败返回 None。"""
    try:
        return jsonp_get(RAD_USER_INFO, {})
    except Exception:
        return None


def get_portal_state(username):
    """
    返回 (状态, 会话信息)：
      online      本机 IP 正以该账号在线
      other       本机 IP 在线，但属于其他账号
      offline     本机 IP 未登录
      unreachable 门户不可达
    """
    res = get_portal_session()
    if res is None:
        return "unreachable", None
    if res.get("error") == "ok" and res.get("online_ip"):
        name = str(res.get("user_name") or "")
        if name == username:
            return "online", res
        if name:
            return "other", res
        # 拿不到用户名时无法确认归属，按未登录处理，允许继续尝试登录
        return "offline", res
    return "offline", res


def get_token(username, ip):
    """获取 challenge(token)。"""
    try:
        res = jsonp_get(CHALLENGE_API, {"username": username, "ip": ip})
    except Exception as e:
        log("获取 challenge 异常：" + str(e))
        return None
    if res and res.get("challenge"):
        return res["challenge"]
    return None


def portal_logout(username, ip):
    """注销本机会话（与门户 JS 相同的参数：action/username/ip/ac_id）。"""
    if not ip:
        ip = ""
    try:
        res = jsonp_get(AUTH_API, {
            "action": "logout",
            "username": username,
            "ip": ip,
            "ac_id": ACID,
        })
    except Exception as e:
        log("注销请求异常：" + str(e))
        return False

    if res is None:
        log("注销接口无有效响应。")
        return False

    if res.get("error") == "ok":
        log("已发送注销请求（%s）。" % (res.get("suc_msg") or "ok"))
    else:
        log("注销失败：%s" % (res.get("error_msg") or res.get("error") or
                             json.dumps(res, ensure_ascii=False)))

    # 等会话从在线表消失（最多 5 秒）
    for _ in range(5):
        state, _ = get_portal_state(username)
        if state != "online":
            return True
        time.sleep(1)
    return False


def do_login(username, password):
    """
    执行一次登录，返回 (是否成功, 类型, 说明)。
    类型：success 登录成功 / already 该 IP 已在线 / error 失败
    """
    ip = get_client_ip()
    if not ip:
        return False, "error", "无法获取客户端 IP（门户不可达？）"

    token = get_token(username, ip)
    if not token:
        return False, "error", "获取 challenge(token) 失败"

    params = build_login_params(username, password, ip, token)
    try:
        res = jsonp_get(AUTH_API, params)
    except Exception as e:
        return False, "error", "认证请求异常：" + str(e)

    if res is None:
        return False, "error", "认证接口无有效响应"

    err = res.get("error") or ""
    suc = res.get("suc_msg") or ""
    err_msg = res.get("error_msg") or ""
    blob = " ".join([err, suc, err_msg])

    if "ip_already_online" in blob:
        return True, "already", "认证接口返回：该 IP 已经在线（%s）" % (suc or err_msg)

    if err == "ok":
        return True, "success", "登录成功" + (("（%s）" % suc) if suc else "")

    # 失败：给出可读原因
    reason = err_msg or err or json.dumps(res, ensure_ascii=False)
    tip = ERROR_TIPS.get(err) or ERROR_TIPS.get(err_msg) or ""
    msg = "登录失败：%s%s" % (reason, tip)

    # 密码错误 / 账号被锁 / 需改密 / 算法异常：重试没有意义，还可能触发账号锁定
    fatal = (err in ("sign_error", "account_locked", "user_must_modify_password")
             or "E2901" in err_msg)
    return False, ("fatal" if fatal else "error"), msg


def wait_until_online(seconds=VERIFY_SECONDS):
    """登录提交后，轮询外网探测地址，确认真的能上网。"""
    deadline = time.time() + seconds
    while True:
        ok, _ = probe_internet()
        if ok:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(2)


# ---------------------------------------------------------------------------
# 状态报告（--check）
# ---------------------------------------------------------------------------
def report_state(username, internet_ok):
    if internet_ok:
        log("已在线，当前可正常上网。")
        return

    state, sess = get_portal_state(username)
    if state == "unreachable":
        log("无法连接认证门户（未连接校园网，或门户暂时不可达）。")
    elif state == "online":
        log("门户显示本机已在线（账号 %s，IP %s），但实际无法上网，会话可能已失效。"
            % (sess.get("user_name"), sess.get("online_ip")))
    elif state == "other":
        log("当前 IP 被账号 %s 占用，本机账号 %s 未在线。"
            % (sess.get("user_name"), username))
    else:
        log("未登录，需要认证。")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def _int_arg(args, name, default):
    if name in args:
        try:
            return int(args[args.index(name) + 1])
        except Exception:
            return default
    return default


def main():
    args = sys.argv[1:]
    check_only = "--check" in args
    wait = _int_arg(args, "--wait", 0)
    interval = _int_arg(args, "--interval", 5)

    log_divider()
    username, password = read_account()
    if not username:
        log("缺少账号配置，退出。")
        sys.exit(1)
    log("开始自动登录：%s  用户 %s" % (PORTAL, username))

    log("正在检测网络连接…")
    internet_ok, _ = probe_internet()

    # --check：只检测状态，不提交登录
    if check_only:
        report_state(username, internet_ok)
        sys.exit(0 if internet_ok else 3)

    # 已经能上网：直接结束
    if internet_ok:
        log("已在线，当前可正常上网，无需认证。")
        sys.exit(0)

    state, sess = get_portal_state(username)

    if state == "unreachable":
        log("无法连接认证门户 %s（请确认已插好网线/连接校园网）。" % PORTAL)
        sys.exit(2)

    if state == "other":
        log("当前 IP 已被账号 %s 占用，无法用 %s 自动登录。" %
            (sess.get("user_name"), username))
        sys.exit(3)

    if state == "online":
        # 门户认为在线，但刚才外网探测失败 -> 会话僵死，注销后重登
        log("门户显示本机已在线，但实际无法上网，判定为会话失效：先注销再重新认证。")
        portal_logout(username, get_client_ip())
        state, sess = get_portal_state(username)
        if state == "other":
            log("注销后本机 IP 被账号 %s 占用，停止自动登录。"
                % sess.get("user_name"))
            sys.exit(3)

    deadline = time.time() + max(wait, 0)
    relogin_tried = False

    while True:
        ok, kind, msg = do_login(username, password)
        log(msg)

        if ok:
            log("正在确认网络是否恢复…")
            if wait_until_online():
                log("已可上网。")
                sys.exit(0)
            log("认证接口返回成功，但 %d 秒内仍无法上网。" % VERIFY_SECONDS)

            # 会话在线却上不了网：再注销重登一次（仅在确实是本账号会话时）
            if kind == "already" and not relogin_tried:
                s2, _ = get_portal_state(username)
                if s2 == "online":
                    log("会话僵死，注销后重试一次…")
                    portal_logout(username, get_client_ip())
                    relogin_tried = True
                    continue
                if s2 == "other":
                    log("该 IP 属于其他账号，不能自动注销。")
                    sys.exit(3)

        if kind == "fatal":
            log("该错误重试无意义，已停止。")
            sys.exit(3)

        if time.time() >= deadline:
            log("达到最大等待时间，仍未成功。")
            sys.exit(3)
        time.sleep(max(interval, 1))


if __name__ == "__main__":
    main()
