// static/js/loading.js
function LoadingWithMask() {
    var mask = "<div id='mask' style='position:absolute; z-index:9000; background-color:#000000; display:none; left:0; top:0;'></div>";
    var loadingImg = "<div id='loadingImg' style='position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 9100;'>";
    loadingImg += "<img src='" + static_url + "image_data/static_image/loading_" + lang + ".gif' style='display: block; margin: 0px auto;' />";
    loadingImg += "</div>";

    $('body').append(mask)
    $('#loadingcontainer').append(loadingImg)

    function resizeMask() {
        var maskHeight = $(document).height();
        var maskWidth = $(document).width();
        $('#mask').css({
            'width': maskWidth,
            'height': maskHeight,
            'opacity': '0.3'
        });
    }

    $(window).resize(function() {
        resizeMask();
    });

    $('#mask').show();
    $('#loadingImg').show();
    resizeMask();


    //마스크 표시
    $('#mask').show();

    //로딩중 이미지 표시
    $('#loadingImg').show();
}

function closeLoadingWithMask() {
    $('#mask, #loadingImg').hide();
    $('#mask, #loadingImg').remove();
}