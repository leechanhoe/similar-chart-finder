// static/js/language.js
function changeLanguage(lang) {
    // 선택한 언어와 현재 언어가 같다면 함수를 빠져나감
    if (lang == currentLang) {
        return;
    }
    
    if (lang == 'ko' || lang == 'en') {
        LoadingWithMask();
        var url = new URL(window.location.href);
        url.searchParams.set('lang', lang);
        window.location.href = url.toString();
    }
}

$(window).on("pageshow", function() {
    closeLoadingWithMask();
});
