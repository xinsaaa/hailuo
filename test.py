import requests

url = "https://api.xiaoheihe.cn/task/sign_v3/get_sign_state?x_os_type=iOS&hkey=bed36963&lang=zh-cn&_time=1772297972&x_app=heybox&device_info=iPhone15ProMax&x_client_type=mobile&nonce=lGoo8OCOnaonluH3HNztOVtH1HJsBUGm&version=1.3.380&time_zone=Asia/Shanghai&heybox_id=60662887&dw=430&os_type=iOS&device_id=295CC58B-857C-42FB-90FE-5768686DA5FD&os_version=26.3&time_zone=Asia/Shanghai"
cookies = {
  "pkey": "MTc3MTM3OTI1Ny42MF82MDY2Mjg4N2JtZmZyYmVzeWhtbnRzbXk__",
  "x_xhh_tokenid": "BlDAQzdbloKQEO7Dg40SBnR85urB7/9zDJlKyBf4bKieLz02JE8w6zhtj/wVUxChV7zjFc2NAvHvx8ks3w7LAtA==",
  "hkey": "d71cc0d1a8be927884391021b5924472",
}

headers = {
  "Host": "api.xiaoheihe.cn",
  "Accept-Encoding": "br;q=1.0, gzip;q=0.9, deflate;q=0.8",
  "Accept": "*/*",
  "Connection": "keep-alive",
  "baggage": "sentry-environment=production,sentry-public_key=cd2481795348588c5ea1fe1284a27c0b,sentry-release=com.max.xiaoheihe%401.3.380%2B1688,sentry-trace_id=3e91211c58c74096ac88b47fc6b5101f",
  "User-Agent": "xiaoheihe/1.3.380 (com.max.xiaoheihe; build:1688; iOS 26.3.0) Alamofire/5.9.0",
  "Accept-Language": "zh-Hans-CN;q=1.0, en-CN;q=0.9, ja-CN;q=0.8",
  "Referer": "http://api.maxjia.com/",
  "sentry-trace": "3e91211c58c74096ac88b47fc6b5101f-a7ba549afbed42c5-0"
}

res = requests.get(url, headers=headers, cookies=cookies)
print(res.text)
