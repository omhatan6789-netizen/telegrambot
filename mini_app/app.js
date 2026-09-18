const tg = window.Telegram?.WebApp;


// =========================================
// Telegram Mini App
// =========================================

if (tg) {

    tg.ready();

    tg.expand();

    if (tg.setHeaderColor) {
        tg.setHeaderColor("#111318");
    }

    if (tg.setBackgroundColor) {
        tg.setBackgroundColor("#111318");
    }
}


// =========================================
// فتح روابط Telegram
// =========================================

function openTelegram(url) {

    if (tg && tg.openTelegramLink) {

        tg.openTelegramLink(url);

    } else {

        window.location.href = url;
    }
}


// =========================================
// بوت نواف
// =========================================

function openBot() {

    openTelegram(
        "https://t.me/lnll0bot"
    );
}


// =========================================
// إضافة للقروب
// =========================================

function addToGroup() {

    openTelegram(
        "https://t.me/lnll0bot?startgroup=true"
    );
}


// =========================================
// إضافة للقناة
// =========================================

function addToChannel() {

    openTelegram(
        "https://t.me/lnll0bot?startchannel=true"
    );
}


// =========================================
// أوامر البوت
// =========================================
//
// هذا يفتح الخاص ويرسل /start commands
// والبوت هو اللي يعرض قائمة الأوامر.
//

function openCommands() {

    openTelegram(
        "https://t.me/lnll0bot?start=commands"
    );
}


// =========================================
// التواصل مع المطور
// =========================================

function contactDeveloper() {

    openTelegram(
        "https://t.me/llalakiah"
    );
}
