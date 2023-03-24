import os
from quart import Quart, Response, send_file
import lastfm
import asyncio
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from urllib.request import urlopen
from io import BytesIO

load_dotenv()
LASTFM_API_KEY = os.getenv('LASTFM_API_KEY')
client = lastfm.Client(LASTFM_API_KEY)

app = Quart(__name__)
FONT = ImageFont.truetype("UbuntuMono-R.ttf", 16)
ALBUM_SIZE = (300, 300)


def filter_album_info(album: dict) -> dict:
    return {
        'artist': album['artist']['name'], 'album': album['name'],
        'pic': album['image'][3]['#text']
    }


def make_chart(filtered_albums: list[dict]) -> Image:
    image_size = (ALBUM_SIZE[0] * 10,
                  ALBUM_SIZE[1] * 10)
    actual_position = (0, 0)
    chart = Image.new('RGB', image_size)
    for album in filtered_albums:
        try:
            album_cover = Image.open(BytesIO(urlopen(album['pic']).read()))
        except ValueError:
            album_cover = Image.new('RGB', ALBUM_SIZE, 'black')

        draw = ImageDraw.Draw(album_cover)
        draw.text((0, 0), f"{album['artist']}", (255, 255, 255), FONT)
        draw.text((0, 16), f"{album['album']}", (255, 255, 255), FONT)
        chart.paste(album_cover, actual_position)

        actual_position = list(actual_position)
        if actual_position[0] == image_size[0] - ALBUM_SIZE[0]:
            actual_position[0] = 0
            actual_position[1] += ALBUM_SIZE[1]
        else:
            actual_position[0] += ALBUM_SIZE[0]
        actual_position = tuple(actual_position)

    chart_byte_arr = BytesIO()
    chart.save(chart_byte_arr, 'jpeg')
    return chart_byte_arr.getvalue()


@app.route('/')
def hello_world():
    return 'Hello world!'


@app.route('/api/monthly/<user>')
async def get_chart(user):
    albums = await client.user_get_top_albums(user, '1month', limit=100)
    albums = albums['topalbums']['album']
    filtered_albums = [filter_album_info(album) for album in albums]
    # return filtered_albums
    print(len(filtered_albums))
    chart = make_chart(filtered_albums)
    response = Response(chart)
    response.headers.set('Content-Type', 'image/jpeg')
    response.headers.set('cache-control', '60')
    return response

if __name__ == '__main__':
    app.run()
