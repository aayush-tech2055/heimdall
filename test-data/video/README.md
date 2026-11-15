# Test video: AcmeLearn ad with planted mistakes

`acmelearn_ad_with_errors.mp4` is a 25-second fictional AcmeLearn ad (synthetic voice, four
scenes). Upload it as `creator@acmelearn.example` after loading the demo data
(`scripts.demo_setup`). It has no captions file, so the caption rule should fire too.

| Time | Speech | On screen | Planted mistakes |
|---|---|---|---|
| 0–8 s | "Hey guys! Still stuck in a boring job? Join Acme Learn, India's top learning app, trusted by 5 million students." | INDIA'S NO. 1 LEARNING APP!! · 5 million students (red background) | "guys", "Acme Learn", "students", superlative, 5 million (fact: 2 million), capitals, "!!", red background |
| 8–16 s | "Our cheap premium plan costs just 199 rupees a month, and it gives you a guaranteed job in 90 days." | Premium plan: just Rs 199 a month · GUARANTEED JOB IN 90 DAYS (green background) | "cheap", "premium plan", wrong price (fact: ₹299), job promise, off-brand colours |
| 16–22 s | "Unlike Coursify and SkillNest, all of our 900 courses are taught by real industry experts." | Better than Coursify and SkillNest · 900 courses (pink on black) | competitors named, 900 courses (fact: 350), off-brand colours |
| 22–25 s | "Sign up today and start learning!" | Acme Learn · Sign up today! (light grey on white) | "Acme Learn", low-contrast text, missing "T&Cs apply." |

Measured on 2026-11-16: first feedback in about 30 seconds, 38 flags, every planted mistake found
with its time range.
