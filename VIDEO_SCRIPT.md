# Direito de Mãe: Pitch Video Script (about 4 min)

Format: you on camera (or as a voiceover) for the framing parts, then a phone screen-recording for the walkthrough.
Read time is about 130 words/min. **[SCREEN]** = what's showing on screen. *Italics* = the Portuguese on the phone.

---

## 0:00–0:20 · Hook
**[SCREEN: face to camera, or a black card with the line "54%"]**

> In Brazil, more than half of new mothers have at least one of their rights broken. Only 8% know all of them.
> Now picture the one with the least protection: a pregnant nanny, no work card, who hears from her boss, "after the baby comes, you're done."

*(Check before recording: FAPESP Feb 2026 figures. If you can't confirm them, say "most new mothers don't know their rights.")*

---

## 0:20–1:05 · What we're solving
**[SCREEN: simple slide. "~6 million domestic workers" · "pregnant" · "often no carteira" · "lives in WhatsApp"]**

> Brazil has about six million domestic workers: nannies, maids, caregivers. Many work without a carteira assinada, and many don't read well.
> The law is actually on their side. From the moment she's pregnant until five months after the birth, she can't be dismissed, **even without a work card**.
> But she doesn't know that. And when she goes to the sindicato or the Defensoria, she arrives with nothing: no dates, no proof, only her word against her employer's.
>
> So we're solving two things: **she doesn't know her rights, and she has no record of what happened.**

---

## 1:05–1:50 · Why this, and the constraints we designed for
**[SCREEN: list builds one line at a time]**

> We built every choice around her real life:
> - **WhatsApp, not an app.** She already uses it. Nothing to download, no login.
> - **Voice first.** She can send a voice note and get one back, so she doesn't need to read well.
> - **No made-up law.** The assistant answers only from a short, curated set of laws and always cites the article. If it isn't sure, it says "I don't know" and sends her to a human.
> - **Dates come from code, not the AI.** Her protection end date is calculated, not guessed. That's the number her job depends on.
> - **It's not a lawyer.** Every time a right looks broken, it says so and sends her to the sindicato first, then the Defensoria.
> - **Her data is hers.** Her number is hashed and no name is stored. One word, APAGAR, deletes everything.
>
> We'll also be honest about one risk: if her employer takes her phone, the chat is visible.

---

## 1:50–3:40 · Walkthrough as the user
**[SCREEN: phone screen recording of the WhatsApp chat. Narrate over it.]**

**1. Voice note** (≈25s)
> Meet Joana. She's a nanny, six months pregnant. She sends a voice note.

*"Sou babá, sem carteira, grávida de 6 meses, o nenê nasce em 20 de janeiro. A patroa disse que vai me mandar embora depois que ele nascer."*

> She gets text and audio back: even without a work card she has rights. She can't be let go until **June 20, 2027**, with the articles cited (LC 150 art. 25; ADCT art. 10, II, b). On first contact it also tells her what it keeps and how to delete it.

**2. Screenshot** (≈20s)
> Her boss texts her. Joana just sends the screenshot.

*"Anotei: 12/11 — patroa disse que vai te dispensar."*

> It's now a dated entry in her record.

**3. Forwarded audio** (≈20s)
> She forwards a voice message from her boss. It's transcribed, and the assistant asks: *"Quem mandou e quando?"* She answers, and the entry is updated.

**4. DOSSIÊ** (≈25s)
> When she's ready to get help, she types one word: DOSSIÊ.

**[SCREEN: open the PDF and scroll slowly]**
> She gets a PDF: a timeline of what happened, her rights with the articles, and the contacts for the sindicato and the Defensoria. It's not proof of her case. It's her evidence, organized, so the person helping her can act on day one.

**5. APAGAR** (≈10s)
> And if she wants it gone: APAGAR. *"Seus dados foram apagados."* Nothing kept.

---

## 3:40–4:15 · How it works + what's next
**[SCREEN: one-line diagram: WhatsApp → Twilio → our server → Claude + ElevenLabs → PDF]**

> Under the hood: WhatsApp through Twilio, Claude for understanding text and images, ElevenLabs for speech in and out, and a small server that keeps the law, the dates and the record under our control.
>
> Next: cover informal and CLT workers, send reminders before key dates, move to an official WhatsApp number, and partner with FENATRAD, the sindicatos and the Defensoria so the dossiê lands where it's needed.

---

## 4:15–4:30 · Close
**[SCREEN: logo + "Direito de Mãe"]**

> The law already protects her. Direito de Mãe makes sure she knows it and can prove what happened.

---

### Recording checklist (in your hour)
- [ ] Record the phone demo first (it's the riskiest part). Do one clean take, then narrate over it afterwards.
- [ ] Before recording, run APAGAR so the chat starts fresh and the consent line shows up.
- [ ] Have the screenshot and the forwarded audio ready on the phone.
- [ ] Hide the ngrok/Twilio sandbox details and your phone number in the recording.
- [ ] Check the 54% / 8% and 6 million figures, or soften the wording.
- [ ] Target 4:00. If it runs long, cut the forwarded-audio step first.
