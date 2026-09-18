const tg = window.Telegram?.WebApp;
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
function openTelegram(url) {
    if (tg && tg.openTelegramLink) {
        tg.openTelegramLink(url);
    } else {
        window.location.href = url;
    }
}
function openBot() {
    openTelegram("https://t.me/lnll0bot");
}
function addToGroup() {
    openTelegram("https://t.me/lnll0bot?startgroup=true");
}
function addToChannel() {
    openTelegram("https://t.me/lnll0bot?startchannel=true");
}
function openCommands() {
    openTelegram("https://t.me/lnll0bot?start=commands");
}
function contactDeveloper() {
    openTelegram("https://t.me/llalakiah");
}
function contactAmira() {
    openTelegram("https://t.me/ax_ai15");
}
