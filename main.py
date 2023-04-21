"""
A simple lastfm chart generator.

Made by @hoxas
MIT License
"""
import os
import re
from io import BytesIO
from urllib.error import HTTPError
from quart import Quart, Response
import lastfm
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from urllib.request import urlopen


def get_env(var: str) -> str:
    env_var = os.getenv(var)
    if not env_var:
        raise ValueError(f"{var} is not set in environment variables or .env file")
    return env_var


load_dotenv()
LASTFM_API_KEY = get_env("LASTFM_API_KEY")
LASTFM_USER = get_env("LASTFM_USER")
EXPIRATION_TIME = get_env("EXPIRATION_TIME")
ALBUM_COVER_SIZE = (300, 300)


class Fetcher:
    def __init__(self, user: str, period: str, chart_shape: str):
        """
        Fetch user's top albums from lastfm api and calculate relevant
        information.

        Args:
            user (str): lastfm username
            period (str): chart period (day, week, month, year, overall)
            chart_shape (str): chart shape (10x10, 8x10, 20x5)
        """

        self.client = lastfm.Client(LASTFM_API_KEY)
        self.user = user

        try:
            self.period = self._parse_period(period)
            self.chart_shape = self._parse_chart_shape(chart_shape)
        except ValueError as e:
            raise e

        self.albums_number = self._calculate_albums_number()
        self.chart_size = self._calculate_chart_size()

    def _parse_period(self, period) -> str:
        """
        Parse period to lastfm api format.

        Raises:
            ValueError: if period is invalid

        Returns:
            str: period in lastfm api format
        """

        period = period.lower()

        if period == "week":
            return "7day"
        elif period == "month":
            return "1month"
        elif period == "year":
            return "12month"
        elif period == "overall":
            return "overall"
        else:
            raise ValueError("Invalid chart period")

    def _parse_chart_shape(self, chart_shape) -> tuple[int, int]:
        """
        Parse chart shape to tuple of ints.

        Raises:
            ValueError: if chart shape is invalid

        Returns:
            tuple[int, int]: chart shape
        """

        chart_shape = chart_shape.lower()

        if re.match(r"(\d+)x(\d+)", chart_shape):
            return tuple(map(int, chart_shape.split("x")))
        else:
            raise ValueError("Invalid chart shape")

    def _calculate_albums_number(self) -> int:
        """
        Calculate number of albums to fetch from lastfm api.

        Returns:
            int: number of albums to fetch
        """

        return self.chart_shape[0] * self.chart_shape[1]

    def _calculate_chart_size(self) -> tuple[int, int]:
        """
        Calculate chart size in pixels.

        Returns:
            tuple[int, int]: chart size in pixels
        """

        return (
            ALBUM_COVER_SIZE[0] * self.chart_shape[0],
            ALBUM_COVER_SIZE[1] * self.chart_shape[1],
        )

    async def fetch(self) -> dict:
        """
        Fetch user's top albums from lastfm api.

        Returns:
            dict: user's top albums
        """

        user_top_albums = await self.client.user_get_top_albums(
            self.user, self.period, limit=self.albums_number
        )

        return user_top_albums


class Chart:
    font = ImageFont.truetype("UbuntuMono-R.ttf", 16)

    def __init__(self, user_top_albums: dict, chart_size: tuple[int, int]):
        self.size = chart_size
        self.position = (0, 0)
        unfiltered_albums = user_top_albums["topalbums"]["album"]
        self.albums = [self._filter_album_info(album) for album in unfiltered_albums]

    def _filter_album_info(self, album: dict) -> dict:
        """
        Filter album info to get artist, album and cover.

        Args:
            album (dict): album info item from lastfm api

        Returns:
            dict: filtered album info
        """

        return {
            "artist": album["artist"]["name"],
            "album": album["name"],
            "pic": album["image"][3]["#text"],
        }

    def _get_album_cover(self, album: dict) -> Image:
        """
        Get album cover image by URL.

        Args:
            album (dict): filtered album info

        Returns:
            Image: album cover image or black image if URL is invalid
        """

        try:
            album_cover = Image.open(BytesIO(urlopen(album["pic"]).read()))
        except (ValueError, HTTPError):
            album_cover = Image.new("RGB", ALBUM_COVER_SIZE, "black")
        return album_cover

    def _write_album_info(self, album: dict, album_cover: Image) -> Image:
        """
        Write album info to album cover image.

        Args:
            album (dict): filtered album info
            album_cover (Image): album cover image

        Returns:
            Image: album cover image with album info
        """

        draw = ImageDraw.Draw(album_cover)
        draw.text((0, 0), f"{album['artist']}", (255, 255, 255), self.font)
        draw.text((0, 16), f"{album['album']}", (255, 255, 255), self.font)
        return album_cover

    def make_chart(self) -> bytes:
        """
        Make chart image.

        Returns:
            bytes: chart image
        """

        chart = Image.new("RGB", self.size)
        for album in self.albums:
            album_cover = self._get_album_cover(album)
            album_cover = self._write_album_info(album, album_cover)

            chart.paste(album_cover, self.position)

            self.position = list(self.position)
            if self.position[0] == self.size[0] - ALBUM_COVER_SIZE[0]:
                self.position[0] = 0
                self.position[1] += ALBUM_COVER_SIZE[1]
            else:
                self.position[0] += ALBUM_COVER_SIZE[0]
            self.position = tuple(self.position)

        chart_byte_arr = BytesIO()
        chart.save(chart_byte_arr, "jpeg")
        return chart_byte_arr.getvalue()


app = Quart(__name__)


@app.route("/")
def hello_world():
    return "Hello world!"


@app.route("/api/<period>/<chart_shape>")
async def get_chart(period: str, chart_shape: str):
    try:
        fetcher = Fetcher(LASTFM_USER, period, chart_shape)
    except ValueError as e:
        return Response(str(e), status=400)

    user_top_albums = await fetcher.fetch()
    await fetcher.client._session.close()

    chart = Chart(user_top_albums, fetcher.chart_size).make_chart()
    response = Response(chart, status=200)
    response.headers.set("Content-Type", "image/jpeg")
    response.headers.set("Age", "0")
    response.headers.set(
        "cache-control", f"public, max-age={EXPIRATION_TIME}, must-revalidate"
    )
    return response


if __name__ == "__main__":
    app.run()
