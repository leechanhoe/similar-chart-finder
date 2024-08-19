// static/js/tooltip.js
function toggleTooltip(event, id) {
    event.stopPropagation();

    var tooltip = document.getElementById(id);
    var rect = tooltip.getBoundingClientRect();

    // 화면의 너비에서 툴팁 너비를 빼서, 툴팁이 화면 밖으로 나가지 않도록 조정합니다.
    if (rect.right > window.innerWidth) {
        tooltip.style.left = 'auto'; // 기존 left 값 제거
        tooltip.style.right = '0'; // 화면 오른쪽 가장자리에 맞춤
    }

    tooltip.style.display = tooltip.style.display === 'block' ? 'none' : 'block';
}

// 전역 클릭 이벤트를 체크하여 tooltip-text가 아닌 곳을 클릭하면 툴팁을 숨깁니다.
window.onclick = function(event) {
    // 모든 툴팁 요소를 가져옵니다.
    var tooltips = document.querySelectorAll('.tooltip-text');
    tooltips.forEach(function(tooltip) {
        // 클릭된 요소가 툴팁 내부가 아니면 툴팁을 숨깁니다.
        if (tooltip.style.display === 'block' && event.target !== tooltip && !tooltip.contains(event.target)) {
            tooltip.style.display = 'none';
        }
    });
}
