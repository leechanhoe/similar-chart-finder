// SDK를 초기화 합니다. 사용할 앱의 JavaScript 키를 설정해 주세요.
Kakao.init('6a4b99066974011ce8e5062716c3b49f');

// SDK 초기화 여부를 판단합니다.
console.log(Kakao.isInitialized());

function kakaoShare(data) {
    Kakao.Link.sendDefault({
        objectType: 'feed',
        content: {
            title: data.title,
            description: data.description,
            imageUrl: data.imageUrl,
            link: {
                mobileWebUrl: data.url,
                webUrl: data.url,
            },
        },
        buttons: [
            {
                title: '웹으로 보기',
                link: {
                    mobileWebUrl: data.url,
                    webUrl: data.url,
                },
            },
        ],
        // 카카오톡 미설치 시 카카오톡 설치 경로이동
        installTalk: true,
    });
}

function shareTwitter(data) {
    var sendText = data.description; // 전달할 텍스트
    var sendUrl = data.url; // 전달할 URL
    window.open("https://twitter.com/intent/tweet?text=" + sendText + "&url=" + sendUrl);
}

function shareFacebook(data) {
    var sendUrl = data.url; // 전달할 URL
    window.open("http://www.facebook.com/sharer/sharer.php?u=" + sendUrl);
}