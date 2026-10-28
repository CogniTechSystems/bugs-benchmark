# Branding assets

The JPG and PNG files are ready to upload. All of them are rendered from
[banner.html](banner.html), a three.js scene that also runs as a live, animated banner when
opened in a browser.

| Asset | Size | Use |
| --- | --- | --- |
| [README banner](readme-banner.png) | 1200 × 630 | Repository README |
| [Social link card](social-1200x630.jpg) | 1200 × 630 | Link preview or landscape post |
| [Social landscape](social-1280x720.jpg) | 1280 × 720 | 16:9 social post or video cover |
| [Wide header](header-1500x500.jpg) | 1500 × 500 | X profile header |
| [LinkedIn banner](linkedin-1584x396.jpg) | 1584 × 396 | LinkedIn profile or company banner |
| [Square post](square-1080x1080.jpg) | 1080 × 1080 | Square feed post |
| [Portrait post](portrait-1080x1350.jpg) | 1080 × 1350 | 4:5 feed post |
| [Story](story-1080x1920.jpg) | 1080 × 1920 | 9:16 story or short-form cover |
| [Profile mark](avatar-400x400.jpg) | 400 × 400 | Profile image, safe for circular crops |

The app serves its favicon from `frontend/public/favicon.svg`; [favicon.svg](favicon.svg) is a
copy for reuse.

## Rendering

Open `banner.html` with these query parameters, at a browser window of the same size, and
take a screenshot:

| Parameter | Values |
| --- | --- |
| `w`, `h` | Image size in pixels |
| `layout` | `wide` (text left, emblem right), `compact` (one-line headline), `square` or `mark` (emblem only) |
| `left` | Left text inset in pixels, to keep text clear of profile pictures |
| `still` | Renders a single fixed frame for screenshots |

For example: `banner.html?layout=wide&w=1200&h=630&still` at a 1200 × 630 window.
