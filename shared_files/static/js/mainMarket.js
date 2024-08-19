// main.js

// Back Forward Cache로 브라우저가 로딩될 경우 혹은 브라우저 뒤로가기 했을 경우 에러 메시지 제거
function handlePageShow() {
    if (event.persisted || (window.performance && window.performance.navigation.type == 2)) {
        $('p.error_message').remove();
    }
}

// input을 건드리면 에러 메세지 없애기
function removeErrorMessageOnInput() {
    $('.form-control').on('input', function() {
        $('p.error_message').remove();
    });
}

// 코드 입력 필드와 datalist 처리
function handleCodeInput() {
    $('#code_input').focus();

    // 미리 datalist의 내용을 저장
    var storedOptions = $('#codes').html();
    $('#codes').empty();

    // 입력 필드에 타이핑을 시작할 때만 datalist 옵션을 복원
    $('#code_input').on('input', function() {
        if ($('#codes').children().length === 0) {
            $('#codes').html(storedOptions);
        }
    });

    // 입력 필드가 포커스를 잃었을 때, 옵션을 다시 비워줍니다 (선택적)
    $('#code_input').blur(function() {
        setTimeout(function() {
            $('#codes').empty();
        }, 100); // 타이밍 이슈로 인한 지연을 추가
    });
}

// 테이블과 이미지 표시를 제어하는 함수
function showTable(type) {
    // 모든 tbody 숨기기
    document.querySelectorAll("tbody").forEach(function(tbody) {
        tbody.style.display = 'none';
    });
    // 모든 이미지 숨기기
    document.getElementById("popular_ranking_img").style.display = 'none';
    document.getElementById("up_ranking_img").style.display = 'none';
    document.getElementById("down_ranking_img").style.display = 'none';

    document.getElementById("popular_button").className = "day_num_button";
    document.getElementById("up_button").className = "day_num_button";
    document.getElementById("down_button").className = "day_num_button";

    // 선택된 타입에 따라 tbody 표시
    document.getElementById("tbody_" + type).style.display = '';

    // 선택된 타입에 따라 관련 이미지만 표시
    document.getElementById(type + "_ranking_img").style.display = 'block';
    document.getElementById(type + "_button").className = "invalid_button";
}

// 초기화 함수
function initialize() {
    $(window).on('load', handlePageShow);
    $(document).ready(function() {
        removeErrorMessageOnInput();
        handleCodeInput();
    });
}

// DOM이 준비되면 초기화 함수 호출
$(document).ready(initialize);