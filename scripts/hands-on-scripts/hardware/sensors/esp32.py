import asyncio
import gc

import machine
import network
import utime
from camera import Camera, FrameSize, GrabMode, PixelFormat
from microdot import Microdot, Response

WIFI_SSID = "dtwin-hotspot"
WIFI_PASSWORD = "<insert-password>"

app = Microdot()

wlan = None
camera = None
capture_lock = None
shutting_down = False

# Default
DEFAULT_FRAME_SIZE = FrameSize.QVGA
DEFAULT_QUALITY = 50

# Current state
current_frame_size = DEFAULT_FRAME_SIZE
current_quality = DEFAULT_QUALITY


# On-board NeoPixel / RGB LED on Freenove ESP32-S3-WROOM.
# GPIO48 is the data pin on this board.
NEOPIXEL_PIN = 48
neopixel_state = False
neopixel_color = (20, 20, 20)  # low-brightness white


def set_neopixel(enabled=None, color=None):
    """Set or toggle the onboard NeoPixel.

    enabled:
        True  -> turn on
        False -> turn off
        None  -> toggle current state
    color:
        Optional (r, g, b) tuple, values 0..255.
    """
    global neopixel_state, neopixel_color

    try:
        import neopixel
        from machine import Pin

        if color is not None:
            neopixel_color = color

        if enabled is None:
            enabled = not neopixel_state

        np = neopixel.NeoPixel(Pin(NEOPIXEL_PIN, Pin.OUT), 1)

        if enabled:
            np[0] = neopixel_color
            neopixel_state = True
        else:
            np[0] = (0, 0, 0)
            neopixel_state = False

        np.write()
        utime.sleep_ms(10)

        print("neopixel:", "on" if neopixel_state else "off", neopixel_color)
        return neopixel_state

    except Exception as exc:
        print("neopixel error:", exc)
        raise


def parse_rgb(value):
    """Parse r,g,b from a query parameter such as '255,0,0'."""
    if not value:
        return None

    try:
        parts = value.split(",")
        if len(parts) != 3:
            return None

        r = max(0, min(255, int(parts[0])))
        g = max(0, min(255, int(parts[1])))
        b = max(0, min(255, int(parts[2])))
        return (r, g, b)

    except Exception:
        return None


def neopixel_off():
    try:
        set_neopixel(False)
    except Exception:
        pass


def connect_wifi(timeout_s=60):
    global wlan

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Optional but often helps after soft resets
    if wlan.isconnected():
        print("already connected:", wlan.ifconfig())
        return

    print("connecting to network...")
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    start = utime.time()
    while not wlan.isconnected():
        status = wlan.status()
        print("wifi status:", status, "ifconfig:", wlan.ifconfig())

        # These constants may exist depending on your MicroPython build
        if status == getattr(network, "STAT_WRONG_PASSWORD", -999):
            raise RuntimeError("wrong Wi-Fi password")
        if status == getattr(network, "STAT_NO_AP_FOUND", -999):
            raise RuntimeError("AP not found")
        if status == getattr(network, "STAT_CONNECT_FAIL", -999):
            raise RuntimeError("Wi-Fi connect failed")

        if utime.time() - start >= timeout_s:
            raise RuntimeError(
                "Wi-Fi connection timeout, status=%s ifconfig=%s" % (status, wlan.ifconfig())
            )

        utime.sleep_ms(500)

    print("network config:", wlan.ifconfig())


def disconnect_wifi(timeout_ms=1000):
    """Try to cleanly detach from the AP before stopping/resetting.

    This helps hostapd/create_ap notice the ESP32 disappeared, but it cannot
    run if power is removed or the hardware reset button is pressed.
    """
    global wlan

    if wlan is None:
        return

    try:
        if wlan.active():
            print("disconnecting Wi-Fi...")

            try:
                wlan.disconnect()
            except Exception as exc:
                print("wifi disconnect error:", exc)

            # Give the Wi-Fi stack a short moment to send the deauth frame.
            start = utime.ticks_ms()
            while wlan.isconnected() and utime.ticks_diff(utime.ticks_ms(), start) < timeout_ms:
                utime.sleep_ms(100)

            try:
                wlan.active(False)
            except Exception as exc:
                print("wifi inactive error:", exc)

            print("Wi-Fi disconnected")
    except Exception as exc:
        print("Wi-Fi cleanup error:", exc)


def shutdown_cleanup():
    """Cleanup used by Ctrl-C, exceptions, and software reset paths."""
    try:
        neopixel_off()
    except Exception as exc:
        print("neopixel cleanup error:", exc)

    try:
        deinit_camera()
    except Exception as exc:
        print("camera cleanup error:", exc)

    try:
        disconnect_wifi()
    except Exception as exc:
        print("wifi cleanup error:", exc)

    try:
        gc.collect()
    except Exception:
        pass


def safe_reset(delay_ms=300):
    """Cleanly disconnect Wi-Fi, then perform a software reset."""
    print("safe reset requested")
    shutdown_cleanup()
    utime.sleep_ms(delay_ms)
    machine.reset()


async def wifi_watchdog():
    while True:
        try:
            if shutting_down:
                return

            if wlan is None or not wlan.isconnected():
                print("wifi lost, reconnecting...")
                connect_wifi()
        except Exception as exc:
            print("wifi watchdog error:", exc)

        await asyncio.sleep(5)


def init_camera(frame_size=DEFAULT_FRAME_SIZE, quality=DEFAULT_QUALITY):
    print("initializing camera...")

    return Camera(
        data_pins=[11, 9, 8, 10, 12, 18, 17, 16],
        vsync_pin=6,
        href_pin=7,
        sda_pin=4,
        scl_pin=5,
        pclk_pin=13,
        xclk_pin=15,
        xclk_freq=8000000,
        powerdown_pin=-1,
        reset_pin=-1,
        pixel_format=PixelFormat.JPEG,
        frame_size=frame_size,
        jpeg_quality=quality,
        fb_count=1,
        grab_mode=GrabMode.WHEN_EMPTY,
    )


def deinit_camera():
    global camera

    if camera is None:
        return

    try:
        camera.deinit()
        print("camera deinitialized")
    except Exception as exc:
        print("camera deinit error:", exc)

    camera = None
    gc.collect()


def reset_camera(frame_size=None, quality=None):
    global camera, current_frame_size, current_quality

    if frame_size is None:
        frame_size = current_frame_size

    if quality is None:
        quality = current_quality

    print("resetting camera...")

    deinit_camera()
    utime.sleep_ms(500)

    camera = init_camera(frame_size=frame_size, quality=quality)

    current_frame_size = frame_size
    current_quality = quality

    # Let the sensor stabilize after reset.
    utime.sleep_ms(300)

    # Warmup captures to stabilize exposure and white balance before serving requests.
    warmup_camera(frames=3)

    print("camera reset done")


def warmup_camera(frames=3):
    global camera

    if camera is None:
        return

    print("warming up camera...")

    for i in range(frames):
        try:
            frame = camera.capture()
            if frame is not None:
                camera.free_buffer()
        except Exception as exc:
            print("warmup capture error:", exc)

        utime.sleep_ms(100)


def parse_frame_size(value):
    if not value:
        return None

    try:
        return getattr(FrameSize, value.upper(), None)
    except Exception:
        return None


def parse_quality(value):
    if not value:
        return None

    try:
        q = int(value)
    except ValueError:
        return None

    return max(10, min(85, q))


def looks_like_jpeg(img):
    return (
        img is not None
        and len(img) > 1000
        and img[0] == 0xFF
        and img[1] == 0xD8
        and img[-2] == 0xFF
        and img[-1] == 0xD9
    )


def capture_once():
    global camera

    if camera is None:
        raise RuntimeError("Camera not initialized")

    frame = camera.capture()

    if frame is None:
        return None

    try:
        img = bytes(frame)
    finally:
        camera.free_buffer()

    return img


async def capture_valid_jpeg(max_attempts=3):
    global camera

    for attempt in range(1, max_attempts + 1):
        gc.collect()

        try:
            await asyncio.sleep_ms(100)
            t0 = utime.ticks_ms()
            img = capture_once()
            elapsed = utime.ticks_diff(utime.ticks_ms(), t0)
            print("capture attempt:", attempt, "ms:", elapsed)

        except Exception as exc:
            print("capture exception:", exc)
            img = None

        if img is not None:
            print("jpeg size:", len(img))

        if looks_like_jpeg(img):
            return img

        print("invalid jpeg on attempt:", attempt)

        # If INVALID JPEG, try to reset camera before next attempt.
        try:
            reset_camera()
        except Exception as exc:
            print("reset after invalid jpeg failed:", exc)

        await asyncio.sleep_ms(200)

    return None


@app.get("/")
async def index(request):
    return (
        "ESP32-CAM server ready\n"
        "Endpoints:\n"
        "  /ping\n"
        "  /snapshot\n"
        "  /snapshot?framesize=QVGA&quality=50\n"
        "  /reset-camera\n"
        "  /reset-board\n"
        "  /shutdown\n"
        "  /neopixel\n"
        "  /neopixel?state=on|off|toggle&color=255,0,0\n"
    )


@app.get("/ping")
async def ping(request):
    return b"ok\n"


@app.get("/neopixel")
async def neopixel_endpoint(request):
    """Toggle or set the onboard NeoPixel.

    Examples:
      /neopixel
      /neopixel?state=toggle
      /neopixel?state=on
      /neopixel?state=off
      /neopixel?state=on&color=255,0,0
    """
    try:
        state = request.args.get("state") or "toggle"
        color = parse_rgb(request.args.get("color"))

        if state == "on":
            enabled = True
        elif state == "off":
            enabled = False
        elif state == "toggle":
            enabled = None
        else:
            return b"invalid state; use on, off, or toggle\n", 400

        is_on = set_neopixel(enabled=enabled, color=color)

        if is_on:
            return "neopixel on color=%s\n" % (neopixel_color,)

        return b"neopixel off\n"

    except Exception as exc:
        print("neopixel endpoint error:", exc)
        return b"neopixel error\n", 500


@app.get("/reset-camera")
async def reset_camera_endpoint(request):
    global capture_lock

    async with capture_lock:
        try:
            reset_camera()
            return b"camera reset done\n"
        except Exception as exc:
            print("manual reset error:", exc)
            return b"camera reset failed\n", 500


async def delayed_safe_reset():
    await asyncio.sleep_ms(200)
    safe_reset()


async def delayed_shutdown():
    """Give the HTTP response time to leave, then disconnect cleanly."""
    global shutting_down

    shutting_down = True
    await asyncio.sleep_ms(300)
    print("shutdown requested")
    shutdown_cleanup()


@app.get("/shutdown")
async def shutdown_endpoint(request):
    """Cleanly stop camera/Wi-Fi without resetting the board.

    Use this before removing power:
      curl http://<esp32-ip>/shutdown

    After this runs, the board stays powered but Wi-Fi is off, so you will
    need to press reset, power-cycle, or use the serial REPL to start again.
    """
    asyncio.create_task(delayed_shutdown())
    return b"shutdown scheduled; Wi-Fi will disconnect\n"


@app.get("/reset-board")
async def reset_board_endpoint(request):
    # Return the response first, then reset shortly after.
    asyncio.create_task(delayed_safe_reset())
    return b"board reset scheduled\n"


@app.get("/snapshot")
async def snapshot(request):
    global camera, current_frame_size, current_quality

    start = utime.ticks_ms()
    print("snapshot request received")

    if camera is None:
        return b"Camera not initialized\n", 503

    try:
        async with capture_lock:
            requested_frame_size = parse_frame_size(request.args.get("framesize"))
            requested_quality = parse_quality(request.args.get("quality"))

            if requested_frame_size is None:
                requested_frame_size = current_frame_size

            if requested_quality is None:
                requested_quality = current_quality

            # Important : si la taille ou qualité change, on reset la caméra
            # au lieu de changer les paramètres à chaud.
            if requested_frame_size != current_frame_size or requested_quality != current_quality:
                print("camera config changed, resetting camera")
                print("new frame size:", requested_frame_size)
                print("new quality:", requested_quality)
                reset_camera(
                    frame_size=requested_frame_size,
                    quality=requested_quality,
                )

            img = await capture_valid_jpeg(max_attempts=3)

            if img is None:
                print("failed to get valid jpeg")
                return b"Invalid JPEG from camera\n", 500

        total = utime.ticks_diff(utime.ticks_ms(), start)
        print("total before return ms:", total)

        return Response(
            body=img,
            headers={
                "Content-Type": "image/jpeg",
                "Content-Length": str(len(img)),
                "Cache-Control": "no-store",
                "Connection": "close",
            },
        )

    except Exception as exc:
        print("snapshot error:", exc)
        return b"Internal server error\n", 500


async def main():
    global camera, capture_lock

    # Make sure the onboard NeoPixel starts off, especially with external 5 V power.
    neopixel_off()

    connect_wifi()

    capture_lock = asyncio.Lock()

    camera = init_camera(
        frame_size=DEFAULT_FRAME_SIZE,
        quality=DEFAULT_QUALITY,
    )

    # Première stabilisation au boot.
    utime.sleep_ms(500)
    warmup_camera(frames=3)

    print("camera initialized")
    print("HTTP server listening on port 80")

    asyncio.create_task(wifi_watchdog())

    await app.start_server(host="0.0.0.0", port=80)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("Ctrl-C received")
finally:
    shutdown_cleanup()
    asyncio.new_event_loop()
