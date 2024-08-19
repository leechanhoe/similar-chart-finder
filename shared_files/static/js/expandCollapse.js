$(document).ready(function(){
    $("#expand_collapse").click(function(){
        $("#total_validation").slideToggle("fast");
        if ($("#expand_collapse").text().includes(window.translations['펼치기'])) {
            $("#expand_collapse").text(window.translations['접기'] + " ↑");
        } else {
            $("#expand_collapse").text(window.translations['펼치기'] + " ↓");
        }
    });
});