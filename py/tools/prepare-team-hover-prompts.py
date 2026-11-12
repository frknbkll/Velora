"""Record the identity-preserving briefs for the team page's alternate portraits."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import json
from pathlib import Path
import re

ACTIONS = [
    "standing with one hand at her waist and giving a small friendly open-palm wave with the other, laughing naturally",
    "standing holding a small plain cream ceramic coffee mug with both hands at waist height, smiling warmly toward someone just beside the camera",
    "standing with a closed neutral beige planner tucked under one arm, her free hand relaxed, with a bright candid smile",
    "standing with one hand resting at her hip and a small fan of neutral fabric swatches in the other, smiling with creative energy",
    "standing holding a closed unmarked sketchbook at her waist with both hands, shoulders relaxed and smiling naturally",
    "standing making a small playful peace sign beside her shoulder with one hand, the other arm relaxed, smiling at the camera",
    "standing with a folded length of cream fabric draped over one forearm, her other hand resting naturally at her hip, caught in a happy laugh",
    "standing in a relaxed three-quarter fashion pose with one hand in her trouser pocket, looking back toward the camera with a wide natural smile",
    "standing holding a small fan of textile color swatches at her waist, giving a modest thumbs-up with the other hand and smiling",
    "standing holding a slim unmarked smartphone at waist level, giving a small friendly wave with her other hand and a warm smile",
    "standing with her arms loosely crossed, shoulders relaxed, body slightly turned and smiling toward someone just off camera",
    "standing holding a small plain coffee mug in one hand, her free hand resting at her waist, caught laughing naturally",
    "standing holding a smartphone down at waist level in one hand and making a playful peace sign near her shoulder with the other, smiling brightly",
    "standing holding a slim smartphone in one hand at waist height, her other arm relaxed, head tilted slightly back in a candid happy laugh",
    "standing making a small heart shape with both hands at upper waist level, smiling warmly at the camera",
    "standing with a closed slim unbranded laptop tucked comfortably under one arm, her other hand resting on it, smiling naturally",
    "standing with an unmarked tablet held at waist level in one hand, her other hand resting at her hip, looking cheerfully toward the camera",
    "standing with one hand giving a small peace sign beside her shoulder, her other hand casually at her waist, smiling with a playful head tilt",
    "standing with a closed beige document folder in one arm and a small welcoming open-palm wave with the other hand, smiling warmly",
    "standing with hands loosely clasped in front at waist height, a relaxed three-quarter pose, head tilted slightly and a genuine broad smile",
    "standing holding two small plain books at waist height, looking just off camera with a happy laugh",
    "standing holding a small plain ceramic coffee mug with both hands at waist height, relaxed shoulders and a joyful natural smile",
    "standing with an unmarked notebook tucked under one arm and a small thumbs-up with the other hand, smiling warmly at the camera",
    "standing in a relaxed three-quarter pose with one hand giving a friendly wave near shoulder height, her other arm relaxed and smiling brightly",
]

html = (ROOT / "html/team.html").read_text(encoding="utf-8")
portraits = re.findall(r'<div class="team-profile-portrait"><img src="([^"]+)"[^>]*>\s*</div>\s*<div class="team-profile-copy">.*?<h3>(.*?)</h3>', html, re.S)
assert len(portraits) == len(ACTIONS) == 24
records = []
for index, ((source, name), action) in enumerate(zip(portraits, ACTIONS)):
    target = "assets/team/hover/" + Path(source).stem + ".jpg"
    prompt = (
        f"Use case: identity-preserve. Asset type: alternate editorial portrait for a fashion-house team card. "
        f"Image 1 is the edit target: the existing portrait of the fictional adult character {name}. "
        f"Create ONE alternate photograph of exactly this same adult woman {action}. "
        "Preserve her exact facial identity, apparent adult age, skin tone, eyes, hair color and hairstyle, "
        "jewelry and existing clothing colors and design. If she wears a hijab, preserve its color and style, "
        "fully covered hair and neck, and modest long sleeves. Change only her pose, expression, the requested prop, "
        "and framing. Keep the same warm light beige seamless studio backdrop and soft diffused natural studio daylight. "
        "Single person, photorealistic premium fashion-house staff photography with real skin pores, realistic fabric "
        "and gentle natural shadows. Vertical 4:5 composition, approximately knees-up or mid-thigh-up standing portrait; "
        "keep her complete head, arms, hands and any prop inside the frame, centered, comfortably filling the photograph. "
        "Natural cheerful expression, a candid moment from the same portrait session. "
        "Avoid CGI, illustration, artificial beauty-filter skin, facial identity drift, a different face or outfit, "
        "extra people, duplicated limbs, malformed hands, extra or fused fingers, warped objects, floating props, "
        "unnatural anatomy, excessive retouching, exaggerated poses, text, logos and watermarks. "
        "Do not create a collage, grid or multiple views. Deliver one finished photograph."
    )
    records.append({"index": index, "name": name, "source": source, "target": target, "action": action, "prompt": prompt})
output = ROOT / "json/reports/imagegen/team-hover-prompts.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({"mode": "built-in image_gen edit", "portraits": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Recorded {len(records)} alternate portrait briefs in {output.relative_to(ROOT)}")
