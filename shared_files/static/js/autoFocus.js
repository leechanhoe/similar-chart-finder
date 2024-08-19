$(document).ready(function() {
    function scrollToInput() {
        var windowHeight = $(window).height();
        var inputOffsetTop = $('#code_input').offset().top;
        var scrollAmount = inputOffsetTop - (windowHeight * 0.1); // 화면 높이의 10% 위로 위치

        $('html, body').animate({
            scrollTop: scrollAmount
        }, 100); // 애니메이션 속도 (0.3초)
    }

    $('#code_input').on('focus', function() {
        setTimeout(scrollToInput, 100); // 키보드가 올라오는 시간만큼 딜레이 (0.3초)
    });
});