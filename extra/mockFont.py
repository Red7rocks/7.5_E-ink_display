import time 
from pathlib import Path
from waveshare_epd import epd7in5_V2_mock
from PIL import Image, ImageDraw, ImageFont

epd = epd7in5_V2_mock.EPD()
epd.init()
epd.Clear()

fontDir = Path("/usr/share/fonts")
fontSize = 46
favorites_file = Path("favorites.txt")

if favorites_file.exists():
    favorites_file.unlink()

print("\n--- Font Viewer Started ---")
print("Press ENTER to skip | Type 'y' and ENTER to save | Ctrl+C to quit\n")

try:
    for file_path in fontDir.glob('**/*'):
        if file_path.is_file() and file_path.suffix.lower() in ['.ttf', '.otf']:
            try:
                image = Image.new('1', (epd.width, epd.height), 255)
                draw = ImageDraw.Draw(image)
                draw.rectangle((0, epd.height // 2, epd.width, epd.height), fill=0)
                
                font = ImageFont.truetype(str(file_path), fontSize)
                draw.text((10, 10), "Hello, dashboard", font=font, fill=0)
                draw.text((10, (epd.height // 2) + 10), "Hello, dashboard", font=font, fill=255)
                draw.text((10, 100), f"{file_path.stem}", font=font, fill=0)
                draw.text((10, (epd.height // 2) + 100), f"{file_path.stem}", font=font, fill=255)

                epd.display(epd.getbuffer(image))
                time.sleep(1)
            except KeyboardInterrupt: 
                raise
            except Exception as e:
                print(f"Skipping {file_path.name}: {e}")
                continue

    epd.sleep()

except KeyboardInterrupt:
    epd.sleep()
    print("\nScript stopped by user. Display put to sleep.")
