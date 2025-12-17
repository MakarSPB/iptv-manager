def generate_m3u(channels) -> str:
    lines = ["#EXTM3U"]
    for ch in channels:
        extinf = f'#EXTINF:-1'
        if ch.tvg_id:
            extinf += f' tvg-id="{ch.tvg_id}"'
        if ch.tvg_name:
            extinf += f' tvg-name="{ch.tvg_name}"'
        if ch.tvg_logo:
            extinf += f' tvg-logo="{ch.tvg_logo}"'
        if ch.group_title:
            extinf += f' group-title="{ch.group_title}"'
        extinf += f', {ch.name}'
        lines.append(extinf)
        lines.append(ch.url)
    return "\n".join(lines)