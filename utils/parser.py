import re
from models import Channel


def parse_m3u(content: str) -> list[Channel]:
    channels = []
    tvg_url = None
    # Ищем url-tvg в первой строке
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if lines and lines[0].startswith('#EXTM3U'):
        match = re.search(r'url-tvg=["'"]([^"'"]+)["'"]', lines[0])
        if match:
            tvg_url = match.group(1)

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF:"):
            extinf = line
            # Извлекаем атрибуты
            match = re.search(r'tvg-id=["\']?([^"\']*)["\']?', extinf)
            tvg_id = match.group(1) if match else None

            match = re.search(r'tvg-name=["\']?([^"\']*)["\']?', extinf)
            tvg_name = match.group(1) if match else None

            match = re.search(r'tvg-logo=["\']?([^"\']*)["\']?', extinf)
            tvg_logo = match.group(1) if match else None

            match = re.search(r'group-title=["\']?([^"\']*)["\']?', extinf)
            group_title = match.group(1) if match else None

            # Ищем имя канала
            name_match = re.search(r",(.*)$", extinf)
            name = name_match.group(1).strip() if name_match else "Unknown"

            # Следующая строка — URL
            i += 1
            if i < len(lines) and not lines[i].startswith("#"):
                url = lines[i]
            else:
                url = ""

            channels.append(
                Channel(
                    name=name,
                    tvg_id=tvg_id,
                    tvg_name=tvg_name,
                    tvg_logo=tvg_logo,
                    group_title=group_title,
                    url=url,
                    tvg_url=tvg_url
                )
            )
        i += 1

    return channels