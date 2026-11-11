"""Check real team-portrait hover, keyboard, touch and unavailable-image behavior."""
import argparse
import base64
import json
from pathlib import Path
import runpy
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
BrowserConnection = runpy.run_path(str(ROOT / "tests/run-product-colors.py"))["BrowserConnection"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=24, help="Optional subset for checking assets while generation is in progress")
    args = parser.parse_args()
    assert 1 <= args.limit <= 24
    records = json.loads((ROOT / "output/imagegen/team-hover-prompts.json").read_text(encoding="utf-8"))["portraits"][:args.limit]
    for record in records:
        assert (ROOT / record["target"]).is_file(), f"Missing alternate portrait: {record['target']}"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    output = ROOT / "tmp"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="team-portraits-", dir=output) as profile:
        process = subprocess.Popen([
            "C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        connection = None
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                        page = next(item for item in json.load(response) if item["type"] == "page")
                    break
                except (OSError, StopIteration):
                    time.sleep(.1)
            else:
                raise RuntimeError("Chrome did not start")
            connection = BrowserConnection(page["webSocketDebuggerUrl"])
            connection.call("Page.enable")
            connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
                window.__teamErrors=[];
                addEventListener('error',e=>{if(e.message)window.__teamErrors.push(e.message)});
                addEventListener('unhandledrejection',e=>window.__teamErrors.push(String(e.reason)));
                addEventListener('securitypolicyviolation',e=>window.__teamErrors.push('CSP '+e.violatedDirective));
            """})

            def evaluate(expression):
                result = connection.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"])
                return result.get("result", {}).get("value")

            def until(expression, message, seconds=15):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if evaluate(expression):
                        return
                    time.sleep(.05)
                raise AssertionError(message + ": " + str(evaluate("({active:document.activeElement?.outerHTML.slice(0,500),pressed:document.querySelector('.team-portrait-swap')?.getAttribute('aria-pressed'),errors:window.__teamErrors})")))

            def navigate():
                connection.call("Page.navigate", {"url": "http://127.0.0.1:8000/team.html"})
                until("document.querySelectorAll('.team-portrait-swap').length===24", "Not all portraits have controls")
                evaluate("document.documentElement.style.scrollBehavior='auto';document.body.style.scrollBehavior='auto';[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Necessary only')?.click()")

            def screenshot(name):
                (output / name).write_bytes(base64.b64decode(connection.call("Page.captureScreenshot", {"format": "png"})["data"]))

            def key(value, code):
                down = {"type": "keyDown", "key": value, "code": value, "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code}
                if value == "Enter":
                    down.update(text="\r", unmodifiedText="\r")
                connection.call("Input.dispatchKeyEvent", down)
                connection.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": value, "code": value, "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code})

            def point(index):
                return evaluate(f"(()=>{{const r=document.querySelectorAll('.team-portrait-swap')[{index}].getBoundingClientRect();return{{x:r.x+r.width/2,y:r.y+r.height/2}}}})()")

            connection.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            connection.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]})
            navigate()
            assert evaluate("matchMedia('(hover:hover) and (pointer:fine)').matches"), "Desktop pointer unavailable"
            assert evaluate("document.documentElement.scrollWidth<=innerWidth"), "Desktop overflow"
            assert evaluate("[...document.querySelectorAll('.team-portrait-swap')].every(b=>b.getAttribute('aria-label').includes(b.querySelector('.team-portrait-hint span:last-child').textContent))"), "Visible control text missing from accessible name"
            assert evaluate("getComputedStyle(document.querySelector('.team-portrait-alternate')).transitionProperty==='opacity' && parseFloat(getComputedStyle(document.querySelector('.team-portrait-alternate')).transitionDuration)>=.25"), "Portrait crossfade missing"
            for index, record in enumerate(records):
                evaluate(f"document.querySelectorAll('.team-portrait-swap')[{index}].scrollIntoView({{block:'center'}})")
                until(f"document.querySelectorAll('.team-portrait-swap')[{index}].querySelector('.team-portrait-original').naturalWidth>0", "Original portrait failed")
                before = evaluate(f"document.querySelectorAll('.team-portrait-swap')[{index}].getBoundingClientRect().height")
                connection.call("Input.dispatchMouseEvent", {"type": "mouseMoved", **point(index)})
                until(f"document.querySelectorAll('.team-portrait-swap')[{index}].getAttribute('aria-pressed')==='true' && getComputedStyle(document.querySelectorAll('.team-portrait-alternate')[{index}]).opacity==='1'", f"Hover failed for {record['name']}")
                assert evaluate(f"document.querySelectorAll('.team-portrait-alternate')[{index}].dataset.originalSrc===" + json.dumps(record["target"])), "Alternate portrait identity changed"
                assert evaluate(f"(()=>{{const image=document.querySelectorAll('.team-portrait-alternate')[{index}],candidate=Number(new URL(image.currentSrc).pathname.match(/-(\\d+)\\.webp$/)?.[1]);return image.complete && image.naturalWidth>0 && image.currentSrc.includes('/assets/responsive/') && candidate>=Math.ceil(image.getBoundingClientRect().width*devicePixelRatio)-1}})()"), "Optimized alternate is missing or undersized"
                after = evaluate(f"document.querySelectorAll('.team-portrait-swap')[{index}].getBoundingClientRect().height")
                assert before == after, "Hover changed card height"
                assert evaluate("document.querySelectorAll('.team-portrait-swap[aria-pressed=true]').length===1"), "Multiple portraits stayed active"
                if index == 0:
                    screenshot("team-portrait-hover-desktop.png")
                connection.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 10, "y": 10})
                until(f"document.querySelectorAll('.team-portrait-swap')[{index}].getAttribute('aria-pressed')==='false'", "Mouse leave did not restore original")

            evaluate("document.querySelector('.team-portrait-swap').scrollIntoView({block:'center'});document.querySelector('.team-portrait-swap').focus()")
            key("Enter", 13)
            until("document.querySelector('.team-portrait-swap').getAttribute('aria-pressed')==='true'", "Keyboard Enter failed")
            key("Escape", 27)
            until("document.querySelector('.team-portrait-swap').getAttribute('aria-pressed')==='false'", "Escape did not restore original")
            connection.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
            until("matchMedia('(prefers-reduced-motion:reduce)').matches && parseFloat(getComputedStyle(document.querySelector('.team-portrait-alternate')).transitionDuration)<=.001", "Reduced motion ignored")

            connection.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            connection.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
            navigate()
            evaluate("document.querySelector('.team-portrait-swap').scrollIntoView({block:'center'})")
            until("document.querySelector('.team-portrait-alternate').naturalWidth>0", "Mobile alternate failed to load")
            assert evaluate("document.documentElement.scrollWidth<=innerWidth"), "Mobile overflow"
            for expected in ("true", "false"):
                touch = point(0)
                connection.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{**touch, "radiusX": 2, "radiusY": 2}]})
                connection.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                until(f"document.querySelector('.team-portrait-swap').getAttribute('aria-pressed')==='{expected}'", "Mobile tap did not toggle")
                if expected == "true":
                    screenshot("team-portrait-hover-mobile.png")
            assert not evaluate("window.__teamErrors"), "Runtime or CSP errors"

            first_alternate = records[0]["target"]
            blocked = evaluate("VeloraImageSources.get(" + json.dumps(first_alternate) + ").srcset.split(', ').map(value=>'*'+value.split(' ')[0]+'*')")
            connection.call("Network.setBlockedURLs", {"urls": [*blocked, "*" + first_alternate + "*"]})
            navigate()
            evaluate("document.querySelector('.team-portrait-swap').scrollIntoView({block:'center'})")
            until("document.querySelector('.team-portrait-swap').disabled", "Failed alternate did not fall back")
            until("document.querySelector('.team-portrait-original').naturalWidth>0 && !document.querySelector('.team-portrait-swap').querySelector('.team-portrait-alternate')", "Fallback hid or broke original")
            assert not evaluate("window.__teamErrors"), "Fallback caused runtime errors"
            result = {"portraitsChecked": len(records), "hoverAndLeave": "passed", "keyboardAndEscape": "passed", "mobileTap": "passed", "layoutShift": "none", "optimizedPortraitIdentityAndPixels": "passed", "reducedMotion": "passed", "unavailableImageFallback": "passed", "runtimeAndCSP": "no errors"}
            (output / "team-portrait-check-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result))
        finally:
            if connection:
                connection.socket.close()
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
