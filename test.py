import requests
import json
import time

timestamp_second = int(time.time())

headers = {
    "yy": "45ccd9788b3ab02bc09de5d410fd1714",
    "sec-ch-ua-platform": "\"Windows\"",
    "Referer": "https://hailuoai.com/",
    "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzIwODYyMTQsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.pGBMA6SSMcXF9sHCSbV5LxozVhmrlEzN10aSrI4VHJ0"
}
url = "https://hailuoai.com/v2/api/multimodal/generate/video"
params = {
    "device_platform": "web",
    "app_id": "3001",
    "version_code": "22203",
    "biz_id": "0",
    "unix": timestamp_second,
    "lang": "zh-Hans",
    "uuid": "91e58793-9f30-4d52-899c-34a6ae4a2278",
    "device_id": "464835835103178752",
    "os_name": "Windows",
    "browser_name": "chrome",
    "device_memory": "8",
    "cpu_core_num": "24",
    "browser_language": "zh-CN",
    "browser_platform": "Win32",
    "screen_width": "1463",
    "screen_height": "915"
}
data = {
    "quantity": 1,
    "parameter": {
        "modelID": "23210",
        "desc": "视频中的人物动起来",
        "fileList": [
            {
                "id": "468814720454438915",
                "url": "https://cdn.hailuoai.com/prod/2026-01-17-13/user/multi_chat_file/63b85db2-d0de-49a6-a796-a96f81f97090.png?x-oss-process=image/resize,p_50/format,webp",
                "name": "屏幕截图 2025-09-06 222439.png",
                "type": "png",
                "frameType": 0
            },
            {
                "id": "468815107101970434",
                "url": "https://cdn.hailuoai.com/prod/2026-01-17-13/user/multi_chat_file/5f58e8ae-ca35-4375-8567-fb1ab3ea23f4.png?x-oss-process=image/resize,p_50/format,webp",
                "name": "屏幕截图 2025-09-06 222439.png",
                "type": "png",
                "frameType": 1
            }
        ],
        "useOriginPrompt": False,
        "resolution": "768",
        "duration": 10,
        "aspectRatio": "16:9"
    },
    "videoExtra": {
        "promptStruct": "{\"value\":[{\"type\":\"paragraph\",\"children\":[{\"text\":\"视频中的人物动起来\"}]}],\"length\":9,\"plainLength\":9,\"rawLength\":9}"
    }
}
data = json.dumps(data, separators=(',', ':'))
response = requests.post(url, headers=headers, params=params, data=data)

print(response.text)
print(response)