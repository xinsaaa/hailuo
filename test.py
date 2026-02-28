#浏览器的完整请求：
# curl 'https://hailuoai.com/v2/api/multimodal/generate/video?device_platform=web&app_id=3001&version_code=22203&biz_id=0&unix=1772281065000&lang=zh-Hans&uuid=91e58793-9f30-4d52-899c-34a6ae4a2278&device_id=464835835103178752&os_name=Windows&browser_name=chrome&device_memory=8&cpu_core_num=24&browser_language=zh-CN&browser_platform=Win32&screen_width=1463&screen_height=915' \
#   -H 'accept: application/json, text/plain, */*' \
#   -H 'accept-language: zh-CN,zh;q=0.9' \
#   -H 'cache-control: no-cache' \
#   -H 'content-type: application/json' \
#   -b 'sensorsdata2015jssdkchannel=%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D; _gc_usr_id_cs0_d0_sec0_part0=52fc59e7-b124-4de4-9881-e7287d7ef434; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%227PO57LZPjOpK%22%2C%22first_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTliOTIwOTU3YThhY2EtMGQ2NDkyZWQ4NzU2ZTEtMjYwNjFhNTEtMTMzODY0NS0xOWI5MjA5NTdhOTI2NTYiLCIkaWRlbnRpdHlfbG9naW5faWQiOiI3UE81N0xaUGpPcEsifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%227PO57LZPjOpK%22%7D%2C%22%24device_id%22%3A%2219b920957a8aca-0d6492ed8756e1-26061a51-1338645-19b920957a92656%22%7D; _token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzU2MjkyNTcsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.MPF35YZwmIVwywGI1RA1jEdnGHd5iPy4Ek3dfQgG920; _gc_s_cs0_d0_sec0_part0=rum=0&expire=1772281965775' \
#   -H 'origin: https://hailuoai.com' \
#   -H 'pragma: no-cache' \
#   -H 'priority: u=1, i' \
#   -H 'referer: https://hailuoai.com/create/text-to-video' \
#   -H 'sec-ch-ua: "Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"' \
#   -H 'sec-ch-ua-mobile: ?0' \
#   -H 'sec-ch-ua-platform: "Windows"' \
#   -H 'sec-fetch-dest: empty' \
#   -H 'sec-fetch-mode: cors' \
#   -H 'sec-fetch-site: same-origin' \
#   -H 'token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzU2MjkyNTcsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ2NDgzNTgzNTEwMzE3ODc1MiIsImlzQW5vbnltb3VzIjpmYWxzZX19.MPF35YZwmIVwywGI1RA1jEdnGHd5iPy4Ek3dfQgG920' \
#   -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36' \
#   -H 'yy: 91af9752c3d176c43d42dec50eecbafb' \
#   --data-raw '{"quantity":1,"parameter":{"modelID":"23204","desc":"人在跳舞","fileList":[],"useOriginPrompt":false,"resolution":"768","duration":6,"aspectRatio":""},"videoExtra":{"promptStruct":"{\"value\":[{\"type\":\"paragraph\",\"children\":[{\"text\":\"人在跳舞 \"}]}],\"length\":4,\"plainLength\":4,\"rawLength\":5}"}}'

#在linux服务器上保存的cookie完整值：
# {
#   "cookies": [
#     {
#       "name": "NEXT_LOCALE",
#       "value": "zh-Hans",
#       "domain": "hailuoai.com",
#       "path": "/",
#       "expires": -1,
#       "httpOnly": false,
#       "secure": false,
#       "sameSite": "Lax"
#     },
#     {
#       "name": "sensorsdata2015jssdkchannel",
#       "value": "%7B%22prop%22%3A%7B%22_sa_channel_landing_url%22%3A%22%22%7D%7D",
#       "domain": ".hailuoai.com",
#       "path": "/",
#       "expires": 1806731488.049993,
#       "httpOnly": false,
#       "secure": false,
#       "sameSite": "Lax"
#     },
#     {
#       "name": "_gc_usr_id_cs0_d0_sec0_part0",
#       "value": "34ccfaa6-7e23-4e09-b149-f767f8d28169",
#       "domain": "hailuoai.com",
#       "path": "/",
#       "expires": 1776762779,
#       "httpOnly": false,
#       "secure": false,
#       "sameSite": "Strict"
#     },
#     {
#       "name": "sensorsdata2015jssdkcross",
#       "value": "%7B%22distinct_id%22%3A%227PO57LZPjOpK%22%2C%22first_id%22%3A%2219c7a52e2c97e4-017980e0bf08c77-26001951-921600-19c7a52e2ca32b%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMTljN2E1MmUyYzk3ZTQtMDE3OTgwZTBiZjA4Yzc3LTI2MDAxOTUxLTkyMTYwMC0xOWM3YTUyZTJjYTMyYiIsIiRpZGVudGl0eV9sb2dpbl9pZCI6IjdQTzU3TFpQak9wSyJ9%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%24identity_login_id%22%2C%22value%22%3A%227PO57LZPjOpK%22%7D%2C%22%24device_id%22%3A%2219c7a52e2c97e4-017980e0bf08c77-26001951-921600-19c7a52e2ca32b%22%7D",
#       "domain": ".hailuoai.com",
#       "path": "/",
#       "expires": 1806731488.060007,
#       "httpOnly": false,
#       "secure": false,
#       "sameSite": "Lax"
#     },
#     {
#       "name": "_gc_s_cs0_d0_sec0_part0",
#       "value": "rum=0&expire=1772172388852",
#       "domain": "hailuoai.com",
#       "path": "/",
#       "expires": 1772172388,
#       "httpOnly": false,
#       "secure": false,
#       "sameSite": "Strict"
#     },
#     {
#       "name": "_token",
#       "value": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzU2Mjc0ODgsInVzZXIiOnsiaWQiOiIzNjI2NDI5MzU3MjgyNzU0NjEiLCJuYW1lIjoi5o6i57Si6ICFNTQ2MSIsImF2YXRhciI6Imh0dHBzOi8vY2RuLmhhaWx1b2FpLmNvbS9wcm9kLzIwMjUtMDMtMTItMjAvdXNlcl9hdmF0YXIvMTc0MTc4MTQ3NDM0NDY4MDc5Mi0yMTExOTE4Nzk0ODY2Njg4MDFvdmVyc2l6ZS5wbmciLCJkZXZpY2VJRCI6IjQ4MTE4MTYwNDI2OTc5MzI4OSIsImlzQW5vbnltb3VzIjpmYWxzZX19.FsfbyZ19Id3xcY_XnqLxdGLUVu-8ZUwHG3RXWo3pu0s",
#       "domain": "hailuoai.com",
#       "path": "/",
#       "expires": 1774763488.977436,
#       "httpOnly": false,
#       "secure": true,
#       "sameSite": "Lax"
#     }
#   ],
#   "origins": [
#     {
#       "origin": "https://hailuoai.com",
#       "localStorage": [
#         {
#           "name": "loginGuideModalShow",
#           "value": "1771578780616"
#         },
#         {
#           "name": "MODELS_SELECTED",
#           "value": "[\"23217\"]"
#         },
#         {
#           "name": "CREATE_WORKSPACE_KEY",
#           "value": "video"
#         },
#         {
#           "name": "sawebjssdkchannel",
#           "value": "{\"latest_event_initial_time\":1771578778309,\"eventList\":[\"web_launch\",\"page_view\",\"link_origin\",\"rd_video_play_result\",\"video_sound_play_click\",\"banner_view\",\"app_active\",\"sample_card_view\",\"login_popup_view\",\"login_click\",\"before_login_fetch\",\"login_result\",\"video_create_zone_view\",\"float_task_view\"]}"
#         },
#         {
#           "name": "EDITOR_TAB_KEY_NEW",
#           "value": "{\"video\":\"i2v\",\"image\":\"t2i\"}"
#         },
#         {
#           "name": "create_form_default_width",
#           "value": "50"
#         },
#         {
#           "name": "USER_HARD_WARE_INFO",
#           "value": "481181604269793289"
#         },
#         {
#           "name": "video_settings_by_model_23217",
#           "value": "{\"resolution\":\"768\",\"duration\":6,\"ratio\":\"\"}"
#         },
#         {
#           "name": "I2V_NEW_MODEL_ID",
#           "value": "23217"
#         },
#         {
#           "name": "CREATE_TAB_RED_DOT_i2v",
#           "value": "1"
#         },
#         {
#           "name": "UNIQUE_USER_ID",
#           "value": "ef0ecbdf-ec3a-4887-9ece-7a1552818037"
#         },
#         {
#           "name": "app_active_tracked",
#           "value": "[\"481181604269793289\"]"
#         }
#       ]
#     }
#   ]
# }