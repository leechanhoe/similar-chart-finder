// static/js/adBanner.js
function setAdBannerWidth() {
    var adBanners = document.getElementsByClassName('adsbygoogle');
    var viewportWidth = Math.min(window.innerWidth, window.innerHeight); // 세로와 가로 중 작은 값

    for (var i = 0; i < adBanners.length; i++) {
        adBanners[i].style.maxWidth = viewportWidth + 'px'; // 여백을 주기 위해 10px을 빼줍니다
    }
}

// 페이지 로드 시 실행
window.onload = setAdBannerWidth;
window.onresize = setAdBannerWidth;
