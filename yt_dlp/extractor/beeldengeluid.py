import re
import time
from http.cookiejar import Cookie
from urllib.parse import parse_qs, urlparse

from .common import InfoExtractor
from ..utils import (
    int_or_none,
    unified_strdate,
)


class BeeldenGeluidIE(InfoExtractor):
    _VALID_URL = r'https?://schatkamer\.beeldengeluid\.nl/serie/(?P<series_id>[^/]+)/(?P<series_slug>[^/]+)/aflevering/(?P<id>[^/?#]+)'
    _TESTS = [{
        'url': 'https://schatkamer.beeldengeluid.nl/serie/2101608030021443931/lingo/aflevering/2101608040029173231',
        'info_dict': {
            'id': '2101608040029173231',
            'ext': 'mp4',
            'title': 'LINGO - LINGO',
            'description': 'md5:1b354b4f3c1961292b6b6f6f2eb7479a',
            'upload_date': '19890105',
            'duration': 1620,
            'thumbnail': r're:^https?://.*\.jpg$',
            'series': 'LINGO',
            'episode': 'LINGO',
        },
    }]

    def _set_cloudfront_cookies(self, m3u8_url):
        """Extract CloudFront signed URL parameters and set them as cookies.

        The CDN converts URL query parameters to signed cookies via a 302 redirect.
        We set the cookies directly to avoid redirect-handling issues.
        """
        parsed = urlparse(m3u8_url)
        params = parse_qs(parsed.query)
        domain = parsed.hostname

        for param_name in ('CloudFront-Policy', 'CloudFront-Signature', 'CloudFront-Key-Pair-Id'):
            value = params.get(param_name, [None])[0]
            if value:
                cookie = Cookie(
                    version=0, name=param_name, value=value,
                    port=None, port_specified=False,
                    domain=f'.{domain.split(".", 1)[1]}', domain_specified=True, domain_initial_dot=True,
                    path='/', path_specified=True,
                    secure=True, expires=int(time.time()) + 3600,
                    discard=False, comment=None, comment_url=None, rest={}, rfc2109=False,
                )
                self._downloader.cookiejar.set_cookie(cookie)

        return f'{parsed.scheme}://{parsed.netloc}{parsed.path}'

    def _real_extract(self, url):
        mobj = self._match_valid_url(url)
        video_id = mobj.group('id')

        webpage = self._download_webpage(url, video_id)

        # Extract m3u8 URL from RSC (React Server Components) inline data
        # The URL uses \u0026 for & characters in the HTML source
        m3u8_url = self._search_regex(
            r'(https://sk-video\.cdn\.beeldengeluid\.nl/[^\s"]+\.m3u8[^\s"]*)',
            webpage, 'stream url')
        m3u8_url = m3u8_url.replace('\\u0026', '&')

        # The CDN uses a Lambda@Edge function that converts signed URL params
        # to signed cookies via a 302 redirect. Set cookies directly.
        base_m3u8_url = self._set_cloudfront_cookies(m3u8_url)

        formats = self._extract_m3u8_formats(base_m3u8_url, video_id, 'mp4', m3u8_id='hls')

        # Extract metadata from embedded RSC data
        episode_title = self._search_regex(
            r'\\"id\\":\\"' + re.escape(video_id) + r'\\",\\"name\\":\\"([^\\"]+)\\"',
            webpage, 'episode title', default=None)

        series_title = self._search_regex(
            r'\\"series\\":\{\\"id\\":\\"[^\\"]+\\",\\"title\\":\\"([^\\"]+)\\"',
            webpage, 'series title', default=None)

        title = f'{series_title} - {episode_title}' if series_title and episode_title else (
            series_title or episode_title or self._html_extract_title(webpage))

        description = self._search_regex(
            r'\\"id\\":\\"' + re.escape(video_id)
            + r'\\",\\"name\\":\\"[^\\"]+\\",\\"start\\":[^,]+,\\"title\\":\\"[^\\"]+\\",\\"description\\":\\"((?:[^\\"]+|\\\\.)*)\\"',
            webpage, 'description', default=None)
        if description:
            description = description.replace('\\\\n', '\n')

        upload_date = unified_strdate(self._search_regex(
            r'\\"publishedAtISO\\":\\"([^\\"]+)\\"',
            webpage, 'upload date', default=None))

        duration = int_or_none(self._search_regex(
            r'\\"durationNumber\\":(\d+)',
            webpage, 'duration', default=None))

        thumbnail = self._search_regex(
            r'\\"poster\\":\\"(https://sk-video[^\\"]+)\\"',
            webpage, 'thumbnail', default=None)

        episode_number = int_or_none(self._search_regex(
            r'\\"episodeNumber\\":(\d+)',
            webpage, 'episode number', default=None))

        return {
            'id': video_id,
            'title': title,
            'description': description,
            'upload_date': upload_date,
            'duration': duration,
            'thumbnail': thumbnail,
            'series': series_title,
            'episode': episode_title,
            'episode_number': episode_number,
            'formats': formats,
        }
