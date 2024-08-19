// static/js/scrolling.js
$(document).ready(function(){
    var totalWidth = $('.scrolling-div div').length * 150;

    function startScrolling() {
        $('.scrolling-div').animate({scrollLeft: totalWidth}, 300000, 'linear', function() {
            $(this).scrollLeft(0);
            startScrolling();
        });
    }
    startScrolling();
});
