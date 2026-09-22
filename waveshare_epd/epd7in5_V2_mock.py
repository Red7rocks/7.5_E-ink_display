from PIL import Image

class EPD:
    def __init__(self):
        self.width = 800
        self.height = 480

    def init(self):
        print("[mock] init() - skipping hardware init")

    def Clear(self):
        print("[mock] Clear()")

    def getbuffer(self, image):
        # real lib packs this into 1-bit buffer; mock just stashes the PIL image
        self._last_image = image
        return image

    def display(self, buffer):
        buffer.save('/home/aburns/Projects/eink-dashboard/images/dashboard_preview.png')
        print("[mock] saved preview to dashboard_preview.png")

    def sleep(self):
        print("[mock] sleep()")
