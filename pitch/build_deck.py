from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

GREEN=RGBColor(0x00,0x7A,0x3D); YELLOW=RGBColor(0xFF,0xCC,0x29); BLUE=RGBColor(0x0B,0x2A,0x6F)
CREAM=RGBColor(0xFB,0xF7,0xEE); INK=RGBColor(0x1E,0x1E,0x1E); MUTED=RGBColor(0x5A,0x5A,0x5A); WHITE=RGBColor(255,255,255)
FONT="Montserrat"

p=Presentation(); p.slide_width=Inches(13.333); p.slide_height=Inches(7.5)
blank=p.slide_layouts[6]

def bg(s,c):
    f=s.background.fill; f.solid(); f.fore_color.rgb=c
def rect(s,x,y,w,h,c,shape=MSO_SHAPE.RECTANGLE):
    r=s.shapes.add_shape(shape,Inches(x),Inches(y),Inches(w),Inches(h)); r.fill.solid(); r.fill.fore_color.rgb=c; r.line.fill.background(); return r
def text(s,x,y,w,h,lines,size,color=INK,bold=False,align=PP_ALIGN.LEFT):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); tf=tb.text_frame; tf.word_wrap=True
    for i,l in enumerate(lines if isinstance(lines,list) else [lines]):
        para=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        para.alignment=align; para.space_after=Pt(size*0.5)
        r=para.add_run(); r.text=l; r.font.size=Pt(size); r.font.color.rgb=color; r.font.bold=bold; r.font.name=FONT
    return tb
def stripe(s):  # thin Brazil stripe at the bottom
    rect(s,0,7.3,4.444,0.2,GREEN); rect(s,4.444,7.3,4.444,0.2,YELLOW); rect(s,8.888,7.3,4.445,0.2,BLUE)
def notes(s,t): s.notes_slide.notes_text_frame.text=t
def kicker(s,t,c=GREEN): text(s,0.8,0.6,11,0.5,t.upper(),14,c,True)

# 1 Title
s=p.slides.add_slide(blank); bg(s,GREEN)
rect(s,8.3,-1.2,6.5,6.5,YELLOW,MSO_SHAPE.DIAMOND)
rect(s,9.85,0.35,3.4,3.4,BLUE,MSO_SHAPE.OVAL)
text(s,0.8,2.4,8,1.4,"Direito de Mãe",66,WHITE,True)
text(s,0.8,3.8,7.5,1.2,"Os direitos dela, no WhatsApp.",28,YELLOW,True)
text(s,0.8,6.3,8,0.5,"For pregnant domestic workers in Brazil",16,WHITE)
notes(s,"Hi, I'm Stephanie. This is Direito de Mãe: her rights, on WhatsApp.")

# 2 Problem - stat
s=p.slides.add_slide(blank); bg(s,CREAM); stripe(s)
kicker(s,"The problem")
text(s,0.8,1.5,5.5,3,"1 in 11",120,GREEN,True)
text(s,0.8,3.6,5.5,1.2,"pregnant women know all their labor rights",24,INK)
text(s,6.9,1.5,5.5,3,"Half+",120,BLUE,True)
text(s,6.9,3.6,5.5,1.2,"had a right violated at work",24,INK)
text(s,0.8,6.4,12,0.5,"FAPESP-funded study, 652 mothers in Campinas, Jundiaí and Recife (Agência FAPESP, Feb 2026)",12,MUTED)
notes(s,"A FAPESP-funded study found only 1 in 11 pregnant women know all their labor rights. More than half had one violated at work. And it's worst for women with less schooling and less support.")

# 3 Who she is
s=p.slides.add_slide(blank); bg(s,BLUE); stripe(s)
kicker(s,"Who she is",YELLOW)
text(s,0.8,1.5,11.5,2,"“Depois que o nenê nascer, você está dispensada.”",44,WHITE,True)
text(s,0.8,3.9,11.5,2.5,["Nanny, maid or caregiver — often no carteira assinada","Lives in WhatsApp. May not read well.","Arrives at the sindicato with no dates and no proof"],24,WHITE)
notes(s,"Meet Joana. She's a nanny, six months pregnant, no work card. Her boss says: after the baby comes, you're done. The law protects her even without a carteira, but she doesn't know it, and she has no record of what happened.")

# 4 What we built
s=p.slides.add_slide(blank); bg(s,CREAM); stripe(s)
kicker(s,"What we built")
text(s,0.8,1.3,11.5,1.4,"A WhatsApp number she can text or voice-note.",40,INK,True)
items=[("Tells her","her rights, with the law cited",GREEN),("Records","what happens, with dates",YELLOW),("Builds","a dossiê PDF for the sindicato",BLUE)]
for i,(a,b,c) in enumerate(items):
    x=0.8+i*4.05
    rect(s,x,3.3,3.7,2.9,WHITE,MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0]=0.08
    rect(s,x,3.3,3.7,0.18,c)
    text(s,x+0.3,3.75,3.2,0.8,a,30,INK,True)
    text(s,x+0.3,4.6,3.2,1.4,b,20,MUTED)
notes(s,"So we built a WhatsApp number. She texts or sends a voice note. It tells her her rights with the law cited, keeps a dated record of what happens, and turns it into a dossiê she can take to the sindicato or the Defensoria.")

# 5 Constraints
s=p.slides.add_slide(blank); bg(s,CREAM); stripe(s)
kicker(s,"Built around her constraints")
rows=[("WhatsApp, voice first","No app, no login, no reading needed"),("Only real law","Answers from curated law, always cites the article"),("Dates from code","Her protection date is calculated, not guessed by AI"),("Not a lawyer","Hands off to the sindicato and Defensoria"),("Her data is hers","Hashed number, no name. APAGAR deletes everything")]
for i,(a,b) in enumerate(rows):
    y=1.35+i*1.12
    rect(s,0.8,y+0.12,0.36,0.36,[GREEN,YELLOW,BLUE,GREEN,YELLOW][i],MSO_SHAPE.OVAL)
    text(s,1.45,y,4.6,0.7,a,24,INK,True)
    text(s,6.0,y+0.04,6.6,0.7,b,20,MUTED)
notes(s,"Every choice comes from her life. WhatsApp and voice, so she doesn't need an app or to read well. It answers only from curated law and cites the article. Her protection date is computed by code, not guessed. It's not a lawyer: it sends her to the sindicato. And one word, APAGAR, deletes everything.")

# 6 Demo
s=p.slides.add_slide(blank); bg(s,GREEN)
rect(s,-1.5,4.2,5,5,YELLOW,MSO_SHAPE.DIAMOND)
text(s,0.8,2.2,11.5,1.5,"Vamos ver.",72,WHITE,True)
text(s,0.8,3.7,11.5,1,"Voice note  →  screenshot  →  DOSSIÊ  →  APAGAR",26,YELLOW,True)
notes(s,"Let's see it as Joana. [Switch to the phone.]\n1. Voice note: 'Sou babá, sem carteira, grávida de 6 meses, o nenê nasce em 20 de janeiro. A patroa disse que vai me mandar embora.' → She hears her rights and the date she's protected until, with the article.\n2. Send the boss's screenshot → 'Anotei.' It's in her record.\n3. Type DOSSIÊ → open the PDF: timeline, rights, sindicato contact.\n4. Type APAGAR → everything's gone.")

# 7 Close
s=p.slides.add_slide(blank); bg(s,BLUE); stripe(s)
text(s,0.8,2.3,11.7,2,"The law already protects her.",48,WHITE,True)
text(s,0.8,3.5,11.7,2,"Now she knows it — and can prove it.",48,YELLOW,True)
text(s,0.8,5.4,11.7,0.6,"Next: all informal workers · date reminders · partners FENATRAD, sindicatos, Defensoria",16,WHITE)
notes(s,"Next: more workers, reminders before key dates, and partnerships with FENATRAD and the Defensoria. The law already protects her. Now she knows it, and can prove it. Obrigada.")

p.save("/Users/stephanie/Documents/Workspace/direito-de-mae/pitch/Direito_de_Mae_pitch.pptx")
