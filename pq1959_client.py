#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PQArt 模型库 (pq1959.com) 客户端 —— 逆向所得协议实现。

协议（已实测）：
  端点 : http://api.pq1959.com/webapi/art/RobotArtPublicService.asmx   (SOAP 1.1)
  命名空间: http://robotart.com/
  参数 : input = Base64( XML请求 )        —— 服务器对 input 先 Base64 解码，再按 XML 解析
  返回 : Base64( XML响应 )

已确认可用的调用：
  GetUserInfoByToken  : input=<ROOT><TOKEN>{token}</TOKEN></ROOT>  -> 用户/授权信息
  GetAppSceneData     : input=<ROOT><TOKEN>{token}</TOKEN></ROOT>  -> 应用场景分类 <option value=GUID>名称</option>
  CheckRobxFile       : input=<ROOT><token>{token}</token><robxGuid>{guid}</robxGuid></ROOT>
                        （当前缓存 token 返回“未登录”，需真正登录会话）

已知常量：
  授权 token（来自 CEF 缓存）: FBB93F4B-1A2D-42AA-811E-F4EDEF33C79F
  会话 Cookie SESSIONID      : B9FB3858-945D-4A73-986F-AEFDAF80ECC6  (.pq1959.com)
  分类“工业机器人实训工作台” : D44C50EC-8BB2-4937-9879-637E5B58B772
  模型文件格式               : .robx
"""
import base64
import re
import json
import sys
import urllib.request

SOAP_URL = "http://api.pq1959.com/webapi/art/RobotArtPublicService.asmx"
NS = "http://robotart.com/"

TOKEN = "FBB93F4B-1A2D-42AA-811E-F4EDEF33C79F"
SESSIONID = "B9FB3858-945D-4A73-986F-AEFDAF80ECC6"
CAT_WORKBENCH = "D44C50EC-8BB2-4937-9879-637E5B58B772"


def _soap(op: str, inner_xml: str, timeout: int = 60) -> str:
    """执行 SOAP 调用，inner_xml 会先 Base64 编码后放入 <input>。返回解码后的响应 XML。"""
    inp = base64.b64encode(inner_xml.encode("utf-8")).decode("ascii")
    env = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><%s xmlns="%s"><input>%s</input></%s></soap:Body></soap:Envelope>'
    ) % (op, NS, inp, op)
    req = urllib.request.Request(
        SOAP_URL,
        data=env.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"%s%s"' % (NS, op),
        },
    )
    raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
    m = re.search(r"<%sResult>(.*?)</%sResult>" % (op, op), raw, re.S)
    val = m.group(1).strip() if m else ""
    if not val:
        return "RAW:" + raw[:500]
    try:
        return base64.b64decode(val).decode("utf-8", "ignore")
    except Exception:
        return "RAW:" + val[:500]


def whoami(token: str = TOKEN) -> str:
    return _soap("GetUserInfoByToken", "<ROOT><TOKEN>%s</TOKEN></ROOT>" % token)


def categories(token: str = TOKEN):
    """返回 [(guid, name), ...] 应用场景分类。"""
    xml = _soap("GetAppSceneData", "<ROOT><TOKEN>%s</TOKEN></ROOT>" % token)
    return re.findall(r'<option value="([^"]+)">([^<]+)</option>', xml)


def check_robx(robx_guid: str, token: str = TOKEN) -> str:
    return _soap(
        "CheckRobxFile",
        "<ROOT><token>%s</token><robxGuid>%s</robxGuid></ROOT>" % (token, robx_guid),
    )


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "whoami"
    if cmd == "whoami":
        print(whoami())
    elif cmd == "categories":
        cats = categories()
        print("分类数: %d" % len(cats))
        for g, n in cats:
            print("  %-40s %s" % (g, n))
        # 保存
        with open("pq1959_categories.json", "w", encoding="utf-8") as f:
            json.dump([{"guid": g, "name": n} for g, n in cats], f, ensure_ascii=False, indent=2)
    elif cmd == "check" and len(argv) > 2:
        print(check_robx(argv[2]))
    else:
        print("usage: pq1959_client.py [whoami|categories|check <robxGuid>]")


if __name__ == "__main__":
    main(sys.argv)
