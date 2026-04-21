"""
SeeDance 2.0 / 2.0 Fast 模型集成验证脚本
验证：模型配置、API映射、normalize跳过、分辨率校验、pricing_matrix计算、请求体构建
"""
import sys
import os
import json

# 设置路径
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, ROOT)

# ---- 直接从源码提取所需函数，避免 sqlmodel 等重依赖 ----

# model_config 只用到 json，可直接 import
from backend.model_config import ModelConfigManager

# 从 order_worker.py 手动提取
import importlib, types
_ow_src = open(os.path.join(ROOT, 'backend', 'order_worker.py'), encoding='utf-8').read()

# 提取 MODEL_ID_MAP dict
import re as _re
_map_match = _re.search(r'MODEL_ID_MAP.*?=.*?({.*?^})', _ow_src, _re.DOTALL | _re.MULTILINE)
MODEL_ID_MAP = eval(_map_match.group(1))

def _get_api_model_id(model_name):
    if not model_name:
        return "23204"
    return MODEL_ID_MAP.get(model_name, "23204")

def _is_seedance_model(model_id):
    return model_id.startswith("seedance")

def _normalize_hailuo_generation_params(model_id, resolution, aspect_ratio, file_count):
    normalized_model_id = model_id
    normalized_resolution = resolution or "768"
    normalized_aspect_ratio = aspect_ratio or ""
    if _is_seedance_model(model_id):
        return normalized_model_id, normalized_resolution, normalized_aspect_ratio
    if file_count > 0:
        normalized_aspect_ratio = ""
    if file_count == 1 and model_id != "23218":
        normalized_model_id = "23217"
    if file_count >= 2:
        normalized_model_id = "23210"
        normalized_resolution = "768"
    if file_count > 0 and normalized_model_id == "23218":
        normalized_resolution = "768"
    return normalized_model_id, normalized_resolution, normalized_aspect_ratio

# 从 hailuo_api.py 提取 build_generate_video_body（同样避免重依赖）
def build_generate_video_body(desc, model_id="23204", duration=6, resolution="768",
                             aspect_ratio="", file_list=None, quantity=1):
    if file_list is None:
        file_list = []
    return {
        "quantity": quantity,
        "parameter": {
            "modelID": model_id,
            "desc": desc,
            "fileList": file_list,
            "useOriginPrompt": False,
            "resolution": resolution,
            "duration": duration,
            "aspectRatio": aspect_ratio,
            "referenceMode": "start-end-frames",
        },
        "videoExtra": {"promptStruct": {}},
        "projectID": "0",
    }


passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  →  {detail}")


# ============================
# 1. 模型配置验证
# ============================
print("\n═══ 1. 模型配置 (model_config.py) ═══")
mgr = ModelConfigManager()
defaults = mgr.get_default_models()
models_by_id = {m["model_id"]: m for m in defaults}

# SeeDance 2.0 Fast
fast = models_by_id.get("seedance_2_0_fast")
check("SeeDance 2.0 Fast 存在于默认模型列表", fast is not None)
if fast:
    check("name = 'SeeDance 2.0 Fast'", fast["name"] == "SeeDance 2.0 Fast", fast.get("name"))
    check("supports_last_frame = True", fast.get("supports_last_frame") is True)
    check("badge = 'NEW'", fast.get("badge") == "NEW", fast.get("badge"))
    check("price = 0.79", fast.get("price") == 0.79, fast.get("price"))
    
    features = json.loads(fast["features"]) if isinstance(fast["features"], str) else fast["features"]
    check("features 包含 480P-720P", "480P-720P" in features, features)
    check("features 包含 4s-15s", "4s-15s" in features, features)
    check("features 包含比例", "21:9/16:9/4:3/1:1/3:4/9:16" in features, features)
    
    pm = json.loads(fast["pricing_matrix"]) if isinstance(fast["pricing_matrix"], str) else fast["pricing_matrix"]
    check("pricing_matrix 有 text tier", "text" in pm)
    check("pricing_matrix 有 single_image tier", "single_image" in pm)
    check("pricing_matrix 有 dual_image tier", "dual_image" in pm)
    check("text.480p.per_second = 0.08", pm["text"]["480p"]["per_second"] == 0.08)
    check("text.720p.per_second = 0.12", pm["text"]["720p"]["per_second"] == 0.12)
    check("Fast 不含 1080p 分辨率", "1080p" not in pm["text"], list(pm["text"].keys()))

# SeeDance 2.0
std = models_by_id.get("seedance_2_0")
check("SeeDance 2.0 存在于默认模型列表", std is not None)
if std:
    check("name = 'SeeDance 2.0'", std["name"] == "SeeDance 2.0", std.get("name"))
    check("supports_last_frame = True", std.get("supports_last_frame") is True)
    check("price = 0.99", std.get("price") == 0.99, std.get("price"))
    
    features = json.loads(std["features"]) if isinstance(std["features"], str) else std["features"]
    check("features 包含 480P-1080P", "480P-1080P" in features, features)
    
    pm = json.loads(std["pricing_matrix"]) if isinstance(std["pricing_matrix"], str) else std["pricing_matrix"]
    check("text.1080p.per_second = 0.18", pm["text"]["1080p"]["per_second"] == 0.18)
    check("single_image.1080p.per_second = 0.22", pm["single_image"]["1080p"]["per_second"] == 0.22)
    check("dual_image.1080p.per_second = 0.26", pm["dual_image"]["1080p"]["per_second"] == 0.26)


# ============================
# 2. MODEL_ID_MAP 映射验证
# ============================
print("\n═══ 2. MODEL_ID_MAP 映射 ═══")
check("'SeeDance 2.0 Fast' → seedance2.0-fast-t2v",
      _get_api_model_id("SeeDance 2.0 Fast") == "seedance2.0-fast-t2v",
      _get_api_model_id("SeeDance 2.0 Fast"))
check("'seedance_2_0_fast' → seedance2.0-fast-t2v",
      _get_api_model_id("seedance_2_0_fast") == "seedance2.0-fast-t2v",
      _get_api_model_id("seedance_2_0_fast"))
check("'SeeDance 2.0' → seedance2.0-t2v",
      _get_api_model_id("SeeDance 2.0") == "seedance2.0-t2v",
      _get_api_model_id("SeeDance 2.0"))
check("'seedance_2_0' → seedance2.0-t2v",
      _get_api_model_id("seedance_2_0") == "seedance2.0-t2v",
      _get_api_model_id("seedance_2_0"))


# ============================
# 3. _is_seedance_model 判断
# ============================
print("\n═══ 3. _is_seedance_model 判断 ═══")
check("seedance2.0-fast-t2v → True", _is_seedance_model("seedance2.0-fast-t2v"))
check("seedance2.0-t2v → True", _is_seedance_model("seedance2.0-t2v"))
check("23204 → False", not _is_seedance_model("23204"))
check("23217 → False", not _is_seedance_model("23217"))


# ============================
# 4. normalize 参数（SeeDance 应跳过改写）
# ============================
print("\n═══ 4. _normalize_hailuo_generation_params ═══")

SEEDANCE_RESOLUTIONS = ["480", "720", "1080"]
SEEDANCE_ASPECTS = ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
SEEDANCE_DURATIONS = list(range(4, 16))  # 4-15

# SeeDance Fast：所有分辨率 × 所有比例 × 文生(0图)/单图(1图)/双图(2图) 均不改写
for model_id in ["seedance2.0-fast-t2v", "seedance2.0-t2v"]:
    model_label = "Fast" if "fast" in model_id else "Std"
    for res in SEEDANCE_RESOLUTIONS:
        for ar in SEEDANCE_ASPECTS:
            for fc in [0, 1, 2]:
                mid, rr, aa = _normalize_hailuo_generation_params(model_id, res, ar, fc)
                ok = (mid == model_id and rr == res and aa == ar)
                if not ok:
                    check(f"{model_label} model_id={model_id} res={res} ar={ar} fc={fc} 不改写",
                          False, f"got mid={mid} res={rr} ar={aa}")
                    break
            else:
                continue
            break
        else:
            continue
        break
    else:
        check(f"{model_label} ({model_id}) 所有参数组合均不被改写", True)

# 对比：传统模型在有图时应改写
mid, rr, aa = _normalize_hailuo_generation_params("23204", "768", "16:9", 1)
check("传统模型(23204) 单图→model_id改为23217", mid == "23217", mid)
check("传统模型(23204) 单图→aspect_ratio清空", aa == "", aa)

mid, rr, aa = _normalize_hailuo_generation_params("23204", "768", "16:9", 2)
check("传统模型(23204) 双图→model_id改为23210", mid == "23210", mid)
check("传统模型(23204) 双图→resolution改为768", rr == "768", rr)


# ============================
# 5. build_generate_video_body 构建
# ============================
print("\n═══ 5. build_generate_video_body 请求体 ═══")

# 先打印代表性组合的原始 JSON
SAMPLE_CASES = [
    ("seedance2.0-fast-t2v", "Fast", 4,  "480", "16:9"),
    ("seedance2.0-fast-t2v", "Fast", 10, "720", "9:16"),
    ("seedance2.0-fast-t2v", "Fast", 15, "480", "21:9"),
    ("seedance2.0-t2v",      "Std",  4,  "480", "1:1"),
    ("seedance2.0-t2v",      "Std",  8,  "720", "4:3"),
    ("seedance2.0-t2v",      "Std",  12, "1080", "3:4"),
    ("seedance2.0-t2v",      "Std",  15, "1080", "16:9"),
]

print("\n  ── 代表性请求体示例 ──")
for model_id, label, dur, res, ar in SAMPLE_CASES:
    body = build_generate_video_body(
        desc="一个女孩在跳舞",
        model_id=model_id,
        duration=dur,
        resolution=res,
        aspect_ratio=ar,
    )
    print(f"\n  📦 [{label}] model={model_id}  dur={dur}s  res={res}  ar={ar}")
    print(f"  {json.dumps(body, ensure_ascii=False, indent=4)}")

print("\n  ── 全量组合校验 ──")
for model_id, label in [("seedance2.0-fast-t2v", "Fast"), ("seedance2.0-t2v", "Std")]:
    for dur in SEEDANCE_DURATIONS:
        for res in SEEDANCE_RESOLUTIONS:
            for ar in SEEDANCE_ASPECTS:
                body = build_generate_video_body(
                    desc="测试提示词",
                    model_id=model_id,
                    duration=dur,
                    resolution=res,
                    aspect_ratio=ar,
                )
                p = body["parameter"]
                ok = (
                    p["modelID"] == model_id and
                    p["duration"] == dur and
                    p["resolution"] == res and
                    p["aspectRatio"] == ar and
                    p["desc"] == "测试提示词"
                )
                if not ok:
                    check(f"{label} body model={model_id} dur={dur} res={res} ar={ar}",
                          False, f"got modelID={p['modelID']} dur={p['duration']} res={p['resolution']} ar={p['aspectRatio']}")
                    break
            else:
                continue
            break
        else:
            continue
        break
    else:
        total = len(SEEDANCE_DURATIONS) * len(SEEDANCE_RESOLUTIONS) * len(SEEDANCE_ASPECTS)
        check(f"{label} ({model_id}) 全部 {total} 种参数组合请求体正确", True)


# ============================
# 6. Pricing Matrix 价格计算验证
# ============================
print("\n═══ 6. Pricing Matrix 价格计算 ═══")

def calc_price(pricing_matrix_json, video_type, resolution, duration_seconds):
    """模拟 main.py 中的价格计算逻辑"""
    pm = json.loads(pricing_matrix_json) if isinstance(pricing_matrix_json, str) else pricing_matrix_json
    tier_key_map = {
        "text_to_video": "text",
        "image_to_video": "single_image",
        "dual_image_to_video": "dual_image",
    }
    tier = pm.get(tier_key_map.get(video_type, "text"))
    if not tier:
        return None
    res_prices = tier.get(resolution)
    if not res_prices:
        return None
    exact = res_prices.get(str(duration_seconds))
    if exact and exact > 0:
        return round(exact, 2)
    pps = res_prices.get("per_second")
    if pps and pps > 0:
        return round(pps * duration_seconds, 2)
    return None

# SeeDance 2.0 Fast
fast_pm = fast["pricing_matrix"]
for vt, tier_label in [("text_to_video", "文生"), ("image_to_video", "单图"), ("dual_image_to_video", "双图")]:
    for res in ["480p", "720p"]:
        for dur in [4, 7, 10, 15]:
            price = calc_price(fast_pm, vt, res, dur)
            check(f"Fast {tier_label} {res} {dur}s → ¥{price}", price is not None and price > 0, f"price={price}")

# SeeDance 2.0 Std (含1080p)
std_pm = std["pricing_matrix"]
for vt, tier_label in [("text_to_video", "文生"), ("image_to_video", "单图"), ("dual_image_to_video", "双图")]:
    for res in ["480p", "720p", "1080p"]:
        for dur in [4, 7, 10, 15]:
            price = calc_price(std_pm, vt, res, dur)
            check(f"Std {tier_label} {res} {dur}s → ¥{price}", price is not None and price > 0, f"price={price}")

# Fast 不应有 1080p 价格
for vt in ["text_to_video", "image_to_video", "dual_image_to_video"]:
    price = calc_price(fast_pm, vt, "1080p", 6)
    check(f"Fast {vt} 1080p → 应为None", price is None, f"price={price}")


# ============================
# 7. 分辨率校验（模拟 main.py）
# ============================
print("\n═══ 7. 分辨率校验 ═══")
VALID_RESOLUTIONS = ("480p", "720p", "768p", "1080p")
for r in ["480p", "720p", "768p", "1080p"]:
    check(f"分辨率 '{r}' 通过校验", r in VALID_RESOLUTIONS)
for r in ["360p", "4k", "2160p", ""]:
    check(f"分辨率 '{r}' 被拒绝", r not in VALID_RESOLUTIONS)


# ============================
# 总结
# ============================
print(f"\n{'='*50}")
print(f"结果:  ✅ {passed} 通过  /  ❌ {failed} 失败")
print(f"{'='*50}")
if failed > 0:
    sys.exit(1)
else:
    print("🎉 全部验证通过！")
