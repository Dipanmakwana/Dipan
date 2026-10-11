import flet as ft
import flet_camera as fc
import flet_geolocator as ftg
import httpx

API = "https://jsonplaceholder.typicode.com"


async def main(page: ft.Page):
    page.title = "Device + API Test"
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 16
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    state = {"lat": None, "lng": None, "photo_size": None, "camera_ready": False}

    # ---------- Location ----------
    geo = ftg.Geolocator()
    page.services.append(geo)

    loc_text = ft.Text("Location: not requested yet", selectable=True)

    async def get_location(e):
        loc_text.value = "Requesting location..."
        page.update()
        try:
            await geo.request_permission()
            pos = await geo.get_current_position()
            state["lat"], state["lng"] = pos.latitude, pos.longitude
            acc = getattr(pos, "accuracy", None)
            acc_txt = f" (±{acc:.0f} m)" if isinstance(acc, (int, float)) else ""
            loc_text.value = f"Lat {pos.latitude:.5f}, Lng {pos.longitude:.5f}{acc_txt}"
        except Exception as ex:
            loc_text.value = f"Location error: {ex}"
        page.update()

    # ---------- Camera ----------
    camera = fc.Camera(expand=True, preview_enabled=True)
    cam_status = ft.Text("Camera: not started")
    photo = ft.Image(src=b"", height=200, fit=ft.BoxFit.CONTAIN, visible=False)

    async def start_camera(e):
        cam_status.value = "Starting camera..."
        page.update()
        try:
            cams = await camera.get_available_cameras()
            if not cams:
                cam_status.value = "No cameras found"
                page.update()
                return
            cam = next(
                (c for c in cams if c.lens_direction == fc.CameraLensDirection.BACK),
                cams[0],
            )
            await camera.initialize(
                description=cam,
                resolution_preset=fc.ResolutionPreset.MEDIUM,
                enable_audio=False,
            )
            state["camera_ready"] = True
            cam_status.value = "Camera ready"
        except Exception as ex:
            cam_status.value = f"Camera error: {ex}"
        page.update()

    async def take_photo(e):
        if not state["camera_ready"]:
            cam_status.value = "Start the camera first"
            page.update()
            return
        try:
            data = await camera.take_picture()
            state["photo_size"] = len(data)
            photo.src = data
            photo.visible = True
            cam_status.value = f"Photo captured ({len(data) / 1024:.0f} KB)"
        except Exception as ex:
            cam_status.value = f"Capture error: {ex}"
        page.update()

    # ---------- API ----------
    api_out = ft.Column(spacing=4)

    def show(*lines):
        api_out.controls = [ft.Text(l, selectable=True) for l in lines]
        page.update()

    async def fetch_posts(e):
        show("Loading posts...")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{API}/posts", params={"_limit": 5})
                r.raise_for_status()
            show(f"GET /posts -> {r.status_code}", *[f"#{p['id']}: {p['title']}" for p in r.json()])
        except Exception as ex:
            show(f"API error: {ex}")

    async def fetch_user(e):
        show("Loading user...")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{API}/users/1")
                r.raise_for_status()
            u = r.json()
            show(f"GET /users/1 -> {r.status_code}", f"{u['name']} ({u['email']})", u["address"]["city"])
        except Exception as ex:
            show(f"API error: {ex}")

    async def send_post(e):
        show("Sending...")
        payload = {
            "title": "Device test",
            "body": f"lat={state['lat']}, lng={state['lng']}, photo_bytes={state['photo_size']}",
            "userId": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(f"{API}/posts", json=payload)
                r.raise_for_status()
            show(f"POST /posts -> {r.status_code}", f"Server replied: {r.json()}")
        except Exception as ex:
            show(f"API error: {ex}")

    # ---------- Layout ----------
    page.add(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Text("1. Location", size=20, weight=ft.FontWeight.BOLD),
                    ft.Button("Get my location", on_click=get_location),
                    loc_text,
                    ft.Divider(),
                    ft.Text("2. Camera", size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(height=300, bgcolor=ft.Colors.BLACK, content=camera),
                    ft.Row([
                        ft.Button("Start camera", on_click=start_camera),
                        ft.Button("Take photo", on_click=take_photo),
                    ], wrap=True),
                    cam_status,
                    photo,
                    ft.Divider(),
                    ft.Text("3. API (jsonplaceholder)", size=20, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Button("GET posts", on_click=fetch_posts),
                        ft.Button("GET user", on_click=fetch_user),
                        ft.Button("POST with location + photo", on_click=send_post),
                    ], wrap=True),
                    api_out,
                ]
            )
        )
    )


ft.run(main)