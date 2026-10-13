"""
Collection of witty, spicy non-veg / double-meaning Hindi & Hinglish jokes
used to humorously reply when users send random chatter text instead of media files.
"""

import random

NONVEG_JOKES = [
    (
        "Doctor: Aapko aisi bimari hai jisme din me 3 baar sex karna padega.\n"
        "Pappu: Lekin doctor sahab, biwi to maanti nahi!\n"
        "Doctor: To kya bimari biwi ko dekh kar hui thi? Dawa bahar se lo!"
    ),
    (
        "Ladki: Tum ladke itne tharki kyu hote ho?\n"
        "Ladka: Arey pagli, jab bhagwan ne dil banaya tha tab thoda niche space bach gaya tha, "
        "to unhone wahan tharak bhar di!"
    ),
    (
        "Master: Santa, 'Kele' aur 'Seb' me kya fark hai?\n"
        "Santa: Sir, Seb khane ke baad doctor ke paas nahi jana padta...\n"
        "Aur Kela agar galat jagah chala jaye to seedha gynaecologist ke paas jana padta hai!"
    ),
    (
        "Biwi: Suno ji, meri ek saheli keh rahi thi ki uske pati raat ko sher ban jaate hain!\n"
        "Pati: Haa, par wo ye batana bhul gayi ki biwi uski din me shikari hoti hai, aur raat me pinjra kholti hai!"
    ),
    (
        "Pappu: Bhabhi ji, bhaiya ghar pe hain kya?\n"
        "Bhabhi: Nahi, wo to market gaye hain. Kyu, kuch kaam tha?\n"
        "Pappu: Bas yahi confirm karna tha! Ab chai pilayengi ya seedha bedroom me chalein?"
    ),
    (
        "Girlfriend: Baby, agar mai mar gayi to tum kya karoge?\n"
        "Boyfriend: Mai to pagal ho jaunga!\n"
        "Girlfriend: Dusri shadi to nahi karoge na?\n"
        "Boyfriend: Pagal aadmi to kuch bhi kar sakta hai baby!"
    ),
    (
        "Ek ladki ne chemist se pucha: Bhaiya, pregnancy test kit kitne ki hai?\n"
        "Chemist: 100 rupaye ki.\n"
        "Ladki: Thoda discount do na!\n"
        "Chemist: Madam, agar ye fail ho gayi to aage ka kharcha lakhon me hoga, 100 rupaye me bargain mat karo!"
    ),
    (
        "Ladka: Tumhara figure kitna sexy hai yaar!\n"
        "Ladki: Tharki kahin ke, sharam nahi aati?\n"
        "Ladka: Arey tarif sunke sharmaana chahiye, gussa kyu ho rahi ho? "
        "Waise konsi gym jaati ho ya bhagwan ne hi special customized banaya hai?"
    ),
    (
        "Pati: Aaj khane me kya banaya hai?\n"
        "Biwi: Jo tumhara mood ho!\n"
        "Pati: Mood to tumhe kachha chabaane ka hai!\n"
        "Biwi: Dhat besharam, pehle bacchon ko so jaane do!"
    ),
    (
        "Doctor: Madam, aapke pati ko poore aaram ki zaroorat hai. Ye neend ki goliya le lijiye.\n"
        "Biwi: Ye unhe kab deni hai doctor sahab?\n"
        "Doctor: Ye unhe nahi, aapko khud khani hain!"
    ),
    (
        "Teacher: Beta, 'Aankh marna' ka sentence banao.\n"
        "Student: Sir, agar ladka maare to chappal padti hai, aur agar ladki maare to dil me ghanti bajti hai!"
    ),
    (
        "Santa ne ek ladki se pucha: Aapka naam kya hai?\n"
        "Ladki: Pooja.\n"
        "Santa: Arey waah! Aaj se meri pooja me koi kami nahi aayegi, har roz subah-shaam aradhana karunga!"
    ),
    (
        "Suhagrat pe Pati: Tum mujhse kitna pyaar karti ho?\n"
        "Biwi: Jitna aap sochna chahte ho!\n"
        "Pati: To kapde kab utaarogi?\n"
        "Biwi: Jab tak tum soch rahe the, tab tak maine panty bhi utaar di!"
    ),
    (
        "Boyfriend: Tumhe kaisa boyfriend pasand hai?\n"
        "Girlfriend: Jo bina bole meri har baat samajh jaye!\n"
        "Boyfriend: Aur bed pe?\n"
        "Girlfriend: Wahan bolne ka waqt kis ke paas hota hai duffer!"
    ),
    (
        "Bhabhi: Devar ji, light chali gayi hai aur andhera ho gaya hai, darr lag raha hai!\n"
        "Devar: Fikar mat karo bhabhi ji, mai to torch leke kab se aapke peeche hi khada hu!"
    ),
]


def get_random_joke() -> str:
    """Return a randomly chosen witty adult joke."""
    return random.choice(NONVEG_JOKES)


def format_joke_card(joke: str) -> str:
    """Format the joke into a playful, witty Telegram card."""
    return (
        "😂 <b>Bhai yahan files bhejo, faltu text nahi!</b>\n\n"
        "Par ab tumne chat kar hi diya hai to ek spicy joke sun lo:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>\"{joke}\"</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <b>Kaam ki baat:</b>\n"
        "• 🎬 Video convert karni hai to video file bhejo.\n"
        "• 📦 Archive unzip karni hai to .zip/.rar bhejo.\n"
        "• 🗜️ Files zip karni hain to /zip mode switch karke files bhejo!"
    )
