import asyncio
import gc

import network
import utime
from camera import Camera, FrameSize, GrabMode, PixelFormat
from microdot import Microdot, Response

WIFI_SSID = ""
WIFI_PASSWORD = ""

app = Microdot()
camera = None
capture_lock = None


wlan = None


def connect_wifi(timeout_s=15):
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        print("network config:", wlan.ifconfig())
        return
    print("connecting to network...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    start = utime.time()
    while not wlan.isconnected():
        if utime.time() - start >= timeout_s:
            raise RuntimeError("Wi-Fi connection timeout")
        utime.sleep_ms(200)
    print("network config:", wlan.ifconfig())


async def wifi_watchdog():
    while True:
        try:
            if wlan is None or not wlan.isconnected():
                print("wifi lost, reconnecting...")
                connect_wifi()
        except Exception as exc:
            print("wifi watchdog error:", exc)
        await asyncio.sleep(5)


def init_camera():
    return Camera(
        data_pins=[11, 9, 8, 10, 12, 18, 17, 16],
        vsync_pin=6,
        href_pin=7,
        sda_pin=4,
        scl_pin=5,
        pclk_pin=13,
        xclk_pin=15,
        xclk_freq=10000000,
        powerdown_pin=-1,
        reset_pin=-1,
        pixel_format=PixelFormat.JPEG,
        frame_size=FrameSize.QVGA,
        jpeg_quality=70,
        fb_count=2,
        grab_mode=GrabMode.WHEN_EMPTY,
    )


@app.get("/")
async def index(request):
    return "ESP32-CAM server ready\n"


@app.get("/ping")
async def ping(request):
    return b"ok\n"


@app.get("/snapshot")
async def snapshot(request):
    global camera, capture_lock
    start = utime.ticks_ms()
    print("snapshot request received")
    if camera is None:
        return b"Camera not initialized\n", 503
    try:
        async with capture_lock:
            gc.collect()
            # 1. Update Framesize if requested
            fs_str = request.args.get("framesize")
            if fs_str:
                # Dynamically get the constant (e.g., camera.FRAME_SVGA)
                fs_val = getattr(FrameSize, f"{fs_str.upper()}", None)
                if fs_val is not None:
                    camera.frame_size = fs_val
                    print(f"Set framesize to {fs_str.upper()}")

            # 2. Update Quality (sharpness) if requested
            q_str = request.args.get("quality")
            if q_str:
                try:
                    q_val = int(q_str)
                    # Clamp between 10 (lowest quality) and 85 (highest quality)
                    q_val = max(10, min(95, q_val))
                    camera.quality = q_val
                    print(f"Set quality to {q_val}")
                except ValueError:
                    pass
            # camera.whitebal = False  # Disable Auto White Balance
            # camera.exposure_ctrl = False  # Disable Auto Exposure Control
            # camera.gain_ctrl = False  # Disable Auto Gain Control
            # camera.raw_gma = False  # Disable Gamma (GMA) Correction
            # camera.lenc = False  # Disable Lens Correction
            # 3. Capture Frame
            t0 = utime.ticks_ms()
            frame = camera.capture()
            if frame is None:
                return b"Capture failed\n", 500
            try:
                img = bytes(frame)
            finally:
                camera.free_buffer()
            print("capture ms:", utime.ticks_diff(utime.ticks_ms(), t0))
            t1 = utime.ticks_ms()
            print("copy/free ms:", utime.ticks_diff(utime.ticks_ms(), t1))

        total = utime.ticks_diff(utime.ticks_ms(), start)
        print("total before return ms:", total)
        return Response(
            body=img,
            headers={
                "Content-Type": "image/jpeg",
                "Content-Length": str(len(img)),
            },
        )
    except Exception as exc:
        print("snapshot error:", exc)
        return b"Internal server error\n", 500


async def main():
    global camera, capture_lock
    connect_wifi()
    capture_lock = asyncio.Lock()
    camera = init_camera()
    print("camera initialized")
    print("HTTP server listening on port 80")
    await app.start_server(host="0.0.0.0", port=80)


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
