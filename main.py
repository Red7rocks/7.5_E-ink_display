from waveshare_epd import epd7in5_V2
import time
import data
import render

data.start_bambu_listener()

CLOCK_REFRESH_INTERVAL = 15      # update the clock every 15 seconds
FULL_REFRESH_EVERY = 360         # Flush the screen every 30 mins

epd = epd7in5_V2.EPD()
epd.init()
epd.Clear()

stats = data.get_stats()
image = render.render_dashboard(stats)
image.save('./images/dashboard_preview.png')
epd.display(epd.getbuffer(image))

epd.init_part() 
partial_count = 0

try:
    while True:
        time.sleep(CLOCK_REFRESH_INTERVAL)
        stats = data.get_stats()
        if partial_count >= FULL_REFRESH_EVERY:
            epd.init()
            image = render.render_dashboard(stats)
            image.save('./images/dashboard_preview.png')
            epd.display(epd.getbuffer(image))
            epd.init_part()
            epd.display_Partial(epd.getbuffer(image), 0, 0, epd.width, epd.height)
            partial_count = 0
        else:
            image = render.render_dashboard(stats)
            image.save('./images/dashboard_preview.png')
            epd.display_Partial(
                epd.getbuffer(image),
                0, 0, epd.width, epd.height
            )
            partial_count += 1


except KeyboardInterrupt:
    epd.sleep()
    print("\nStopped. Display asleep.")
