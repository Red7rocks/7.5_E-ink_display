from dotenv import load_dotenv
import os
from PIL import Image, ImageDraw, ImageFont
from data import WEATHER_ICON_MAP_DAY, WEATHER_ICON_MAP_NIGHT, get_weather_icon_category
import datetime

EPD_WIDTH = 800
EPD_HEIGHT = 480
FONT_PATH = os.environ.get("main_font")
DOCKER_FONT_PATH = os.environ.get("condensed_font")
WEATHER_FONT_PATH = os.environ.get("weather_font")

font_weather_icon = ImageFont.truetype(WEATHER_FONT_PATH, 65)
font_day = ImageFont.truetype(FONT_PATH, 60)
font_large = ImageFont.truetype(FONT_PATH, 45)
font_temp = ImageFont.truetype(FONT_PATH, 40)
font_header = ImageFont.truetype(FONT_PATH, 30)
font_paragraph = ImageFont.truetype(FONT_PATH, 25)
font_small = ImageFont.truetype(FONT_PATH, 20)
font_docker = ImageFont.truetype(DOCKER_FONT_PATH, 20)
font_mini = ImageFont.truetype(DOCKER_FONT_PATH, 15)

CLOCK_X = 8
CLOCK_Y = 5

WEATHER_X = 730
WEATHER_Y = 5

DATE_X = 8
DATE_Y = 55

desktop_block_ystart = 110
printer_block_xstart = 410 
printer_block_ystart = desktop_block_ystart
server_block_ystart = 260
docker_section_ystart = 257
pi_block_ystart = 375
text_space = 35

STATUS_LABELS = {
    "RUNNING": "Printing",
    "PAUSE": "Paused",
    "FINISH": "Finished",
    "IDLE": "Idle",
}

def render_dashboard(stats):
    image = Image.new('1', (EPD_WIDTH, EPD_HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    drawBorders(draw)

    pi = stats["pi"]
    server = stats["server"]
    desktop = stats["desktop"]
    printer = stats["printer"]
    weather = stats["weather"]

    # Clock block
    currentDate = datetime.datetime.now();
    draw.text((CLOCK_X, CLOCK_Y), stats["time"], font=font_large, fill=0)
    draw.text((DATE_X, DATE_Y), currentDate.strftime("%b %d, %Y"), font=font_header, fill=0)
    draw.text((400, 50), currentDate.strftime("%A"), font=font_day, fill=0, anchor="mm")

    #Weather block
    category = get_weather_icon_category(weather["weather_code"])
    icon_map = WEATHER_ICON_MAP_NIGHT if weather.get("is_night") else WEATHER_ICON_MAP_DAY
    icon_char = icon_map.get(category, "?")
    draw.text((745, 50), icon_char, font=font_weather_icon, fill=0, anchor="mm")

    temp_str = f"{weather['temp']}°F" if weather['temp'] is not None else "--°F"
    draw_text_right_aligned(draw, 690, CLOCK_Y, temp_str, font=font_large)

    precip_str = f"{weather['precip_chance']}% PoP" if weather['precip_chance'] is not None else ""
    draw_text_right_aligned(draw, 690, DATE_Y, precip_str, font=font_header)

    # Desktop block
    draw.text((10, desktop_block_ystart), "Desktop:", font=font_header, fill=0)
    draw.text((20, desktop_block_ystart + text_space), f"CPU: {desktop.get('cpu_load', '?')}%  Temp: {desktop.get('cpu_temp', '?')}°C", font=font_paragraph, fill=0)
    draw.text((20, desktop_block_ystart + (text_space * 2)), f"GPU: {desktop.get('gpu_load', '?')}%  Temp: {desktop.get('gpu_temp', '?')}°C", font=font_paragraph, fill=0)
    draw.text((20, desktop_block_ystart + (text_space * 3)), f"Mem: {desktop.get('mem_used_pct', '?')}%", font=font_paragraph, fill=0)

    # Server block
    draw.text((10, server_block_ystart), "Server:", font=font_header, fill=0)
    draw.text((20, server_block_ystart + text_space), f"CPU: {server.get('cpu_load', '?')}%  Temp: {server.get('cpu_temp', '?')}°C", font=font_paragraph, fill=0)
    draw.text((20, server_block_ystart + (text_space * 2)), f"Mem: {server.get('mem_used_pct', '?')}%", font=font_paragraph, fill=0)

    # Raspberry Pi block
    draw.text((10, pi_block_ystart), "Raspberry Pi:", font=font_header, fill=0)
    draw.text((20, pi_block_ystart + text_space), f"CPU: {pi.get('cpu_load', '?')}%  Temp: {pi.get('cpu_temp', '?')}°C", font=font_paragraph, fill=0)
    draw.text((20, pi_block_ystart + (text_space * 2)), f"Mem: {pi.get('mem_used_pct', '?')}%", font=font_paragraph, fill=0)

    # 3D printer block
    draw_printer_block(draw, printer)

    # 3D printer block
    draw_docker_columns(draw, stats, docker_section_ystart)

    return image

def draw_printer_block(draw, printer):
    draw.text((printer_block_xstart, printer_block_ystart), "3D Printer:", font=font_header, fill=0)

    state = printer.get("display_state", "Unknown")
    progress = printer.get("progress")
    is_running = state == "RUNNING" and progress is not None
    is_finished = state == "FINISH"

    status_label = STATUS_LABELS.get(state, "Not connected" if state == "Unknown" else "Not running")

    if is_finished:
        progress_display = 100
    elif progress is not None:
        progress_display = progress
    else:
        progress_display = 0

    # Only show the "- X% complete" text while running or finished, not when idle
    if is_running or is_finished:
        status_text = f"{status_label} - {progress_display}% complete"
    else:
        status_text = status_label

    draw.text(
        (printer_block_xstart + 10, printer_block_ystart + text_space),
        status_text,
        font=font_paragraph, fill=0
    )

    bar_x, bar_y = printer_block_xstart + 10, printer_block_ystart + (text_space * 2)
    bar_width, bar_height = 350, 25

    draw.rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), outline=0, width=2)

    if is_running or is_finished:
        fill_pct = progress_display if is_running else 100
        filled_width = int(bar_width * (fill_pct / 100))
        if filled_width > 0:
            draw.rectangle((bar_x, bar_y, bar_x + filled_width, bar_y + bar_height), fill=0)

    detail_y = bar_y + bar_height + 5

    if is_running:
        remaining_min = printer.get("remaining_min")
        layer = printer.get("layer")
        total_layers = printer.get("total_layers")

        parts = []
        if remaining_min is not None:
            hours, mins = divmod(int(remaining_min), 60)
            parts.append(f"{hours}h {mins}m left" if hours else f"{mins}m left")
        if layer is not None and total_layers is not None:
            parts.append(f"Layer {layer}/{total_layers}")

        if parts:
            draw.text((bar_x, detail_y), "   ".join(parts), font=font_small, fill=0)

def draw_docker_columns(draw, stats, y_start):
    left_x = 410
    right_x = 610
    col_width = 200
    row_height = 24

    server_containers = stats["server"].get("containers", [])
    pi_containers = stats.get("pi_docker", [])

    draw.text((502, y_start), "Server Containers", font=font_docker, fill=0, anchor="mm")
    draw.text((700, y_start), "Pi Containers", font=font_docker, fill=0, anchor="mm")

    header_offset = 20

    for i, container in enumerate(server_containers):
        y = y_start + header_offset + (i * row_height)
        indicator = "●" if container["up"] else "○"
        name = truncate_name(container["name"])
        draw.text((left_x, y), f"{indicator} {name}", font=font_mini, fill=0)

    for i, container in enumerate(pi_containers):
        y = y_start + header_offset + (i * row_height)
        indicator = "●" if container["up"] else "○"
        name = truncate_name(container["name"])
        draw.text((right_x, y), f"{indicator} {name}", font=font_mini, fill=0)

def truncate_name(name, max_length=20):
    if len(name) > max_length:
        return name[:max_length] + "..."
    return name

def draw_text_right_aligned(draw, right_x, y, text, font, fill=0):
    text_width = draw.textlength(text, font=font)
    x = right_x - text_width
    draw.text((x, y), text, font=font, fill=fill)

def drawBorders(draw):
    draw.rectangle(
        (0, 100, 800, 480),
        outline=0, width=4
    )
    draw.line((400, 100, 400, 480), fill=0, width=4)
    draw.line((600, 240, 600, 480), fill=0, width=4)
    draw.line((400, 240, 800, 240), fill=0, width=4)
    draw.line((400, 240 + 30, 800, 240 + 30), fill=0, width=4)
    draw.line((0, desktop_block_ystart + (text_space * 4) + 5, 400, desktop_block_ystart + (text_space * 4) + 5), fill=0, width=4)
    draw.line((0, server_block_ystart + (text_space * 3) + 5, 400, server_block_ystart + (text_space * 3) + 5), fill=0, width=4)
