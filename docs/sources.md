# Sources

External figures quoted anywhere in my write-up, with publisher, title, URL and the date I accessed them. These figures are context, not inputs. `docs/validation.md` compares my own computed numbers against them, and `config.PUBLISHED_VALIDATION_FIGURES` holds the values as code-level constants.

## Grayscale: BTC 90-day correlation with Nasdaq and gold

| Publisher | Title | URL | Accessed |
|---|---|---|---|
| Bloomingbit (reporter JH Kim, citing Cointelegraph/Grayscale) | "Grayscale Says Bitcoin's 90-Day Correlation With Nasdaq Falls to 33%, Gold Link Rises to 50%" | https://en.bloomingbit.io/feed/news/119627 | 2026-09-18 |
| Benzinga | "Bitcoin Decoupling From Nasdaq, Says Grayscale as 'Debasement Trade' Comes Into Focus" | https://www.benzinga.com/crypto/cryptocurrency/26/09/61593730/bitcoin-gold-nasdaq-composite-correlation-debasement-trade-hedge | 2026-09-18 |

Quoted figures (Bloomingbit, published 2026-09-02): "Bitcoin's 90-day correlation with the Nasdaq fell to 33% from 60%. Over the same period, Bitcoin's correlation with gold rose to about 50%." The Bloomingbit quote does not say whether "Nasdaq" means the Composite or the Nasdaq-100. Benzinga's title names "Nasdaq Composite", so `docs/validation.md` compares this figure against my `BTC_NASDAQ` series (`^IXIC`) and not the Nasdaq-100 series. Benzinga's article text returned an HTTP 403 when I fetched it. The Composite reading rests on the title alone, not on a quoted sentence.

## Bitwise: BTC 90-day correlation with gold and Nasdaq-100

| Publisher | Title | URL | Accessed |
|---|---|---|---|
| The Block | "Bitcoin-gold correlation hits six-year high, but analysts question whether equity decoupling will last" | https://www.theblock.co/news/markets/2026-09-03-bitcoin-gold-correlation-hits-six-year-high-but-analysts-question-whether-equity-decoupling-will-last-413437 | 2026-09-18 |
| 24/7 Wall St. (Sam Daodu, syndicated via Yahoo Finance) | "Bitcoin's Correlation With Gold Just Hit a Six-Year High. Is BTC Finally Digital Gold?" | https://finance.yahoo.com/markets/crypto/articles/bitcoin-correlation-gold-just-hit-153154868.html | 2026-09-18 |

Quoted figures: The Block (published 2026-09-03) quotes André Dragosch (Director, Head of Research Europe, Bitwise). It gives the BTC-gold 90-day correlation as "~+0.50", described as a six-year high, and the BTC-Nasdaq-100 90-day correlation as "fallen to around 0.33". 24/7 Wall St. (published 2026-09-15) reports the same Bitwise report, dated September 3 and using Bloomberg data "through August 31". It gives the gold correlation as "+0.50... the highest since 2020" and the Nasdaq-100 correlation as "about +0.30, the lowest in a year". Both outlets attribute the figures to Bitwise's own research (Bloomberg data, April 2015 through the end of August 2026). I have not verified them independently.

A third outlet, news.bitcoin.com ("Bitcoin Is Trading Like Gold Again, Bitwise Says the Last Time Was 2020", citing Bitwise CIO Matt Hougan), turned up in the same search. I did not fetch it, so I do not cite its numbers.

## Limitations of these sources

1. **I did not locate Grayscale's primary document.** Both citations above are secondary reporting of Grayscale's research. I did not find the September 2026 research note on research.grayscale.com. An earlier commentary from January 2026, "Bitcoin and the Debasement Trade", exists there, but it is not the source of the 33% and 50% figures. Read every Grayscale figure in `docs/validation.md` as "per Bloomingbit and Benzinga, reporting Grayscale", not "per Grayscale directly".
2. **The secondary outlets disagree on the exact Bitwise figures**, although they describe the same report. Both fetched outlets give the gold correlation as about 0.50. A third, unfetched outlet reported 0.56 for the same reading. The Nasdaq-100 correlation is 0.30 in 24/7 Wall St. and 0.33 in The Block. `docs/validation.md` uses 0.50 and 0.30, the values common to both fetched sources, and treats 0.33 as a disclosed variance between outlets, not as a fifth comparison row. The variance comes from the journalism, not from my method.
3. **I do not reproduce the "fell from X" trajectory values.** Grayscale (60% to 33%) and Bitwise ("one-year low", "six-year high") describe a change over an unstated start date. `docs/validation.md` reproduces only the reported endpoint value, because inventing a start date to compute a matching trajectory would be a form of fabrication.
