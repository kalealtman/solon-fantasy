Drop one image per award here, named to match the `image_slug` column in
`config/coaches_poll_awards.csv`. Any of `.jpg` / `.jpeg` / `.png` / `.webp`
works -- `build_site.py` picks whichever extension it finds.

Current slugs (add a new row to `coaches_poll_awards.csv` for future awards):

- `mel_kiper.*` -- Mel Kiper Award (Best Drafter)
- `phil_jackson.*` -- Phil Jackson Award (Best In-Season Manager)
- `used_car_salesman.*` -- Used Car Salesman (Best Trader)
- `skip_bayless.*` -- Skip Bayless Award (Elite Trash Talker)
- `hold_my_beer.*` -- Hold My Beer Award (Most Aggressive GM)
- `antonio_brown.*` -- Antonio Brown Award (Biggest Wild Card)

Images are embedded into the built site as base64 data URIs (the site is a
single self-contained HTML file), so keep them reasonably small -- a few
hundred KB each is plenty for a card-sized image. Missing an image for an
award is fine; the site falls back to that award's emoji.
