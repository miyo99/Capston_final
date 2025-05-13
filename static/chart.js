// 📊 도넛 차트 그리기
const ctx = document.getElementById('riskChart').getContext('2d');

const riskChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
        labels: ['양호', '경미', '주의', '심각', '위험'],
        datasets: [{
            label: '위험도 분포',
            data: riskDataFromServer,  // Flask에서 넘긴 데이터
            backgroundColor: [
                '#5cb85c', // green
                '#f0ad4e', // yellow
                '#f7b731', // orange
                '#fd7e14', // dark orange
                '#d9534f'  // red
            ],
            borderWidth: 1
        }]
    },
    options: {
        responsive: true,
        plugins: {
            legend: {
                position: 'right',
                labels: {
                    color: '#ffffff',
                    font: {
                        size: 16
                    }
                }
            },
            title: {
                display: true,
                text: '위험도 분포 (도넛형)',
                color: '#ffffff',
                font: {
                    size: 20
                }
            }
        }
    }  
});


// 🖼️ 이미지 페이지네이션 렌더링
const resultImages = window.resultImages || [];         // Flask에서 넘겨받은 이미지 리스트
const dangerLevels = window.dangerLevels || {};         // Flask에서 넘겨받은 위험도 정보

const perPage = 10;      // 한 페이지당 10장
let currentPage = 0;

function renderPage() {
    const grid = document.getElementById("imageGrid");
    grid.innerHTML = "";

    const start = currentPage * perPage;
    const end = start + perPage;
    const pageItems = resultImages.slice(start, end);

    pageItems.forEach(img => {
        const card = document.createElement("div");
        card.className = "card";

        const image = document.createElement("img");
        image.src = `/results/${img}`;  // Flask 경로에 맞게 조정
        image.alt = "crack result";
        card.appendChild(image);

        const info = document.createElement("div");
        info.className = "info";

        const name = document.createElement("span");
        name.className = "filename";
        const shortName = img.substring(0, 5);
        name.textContent = shortName;

        const risk = document.createElement("span");
    risk.className = "risk";

        if (dangerLevels[img]) {
            risk.textContent = `위험도: ${dangerLevels[img].level} - ${dangerLevels[img].desc}`;
        } else {
            risk.textContent = `위험도: 정보 없음`;
        }
        card.appendChild(info);
        grid.appendChild(card);

        info.appendChild(name);
        info.appendChild(risk);
        
    });

    // 페이지 번호 표시
    const pageNumber = document.getElementById("pageNumber");
    if (pageNumber) {
        pageNumber.textContent = currentPage + 1;
    }
}

function nextPage() {
    if ((currentPage + 1) * perPage < resultImages.length) {
        currentPage++;
        renderPage();
    }
}

function prevPage() {
    if (currentPage > 0) {
        currentPage--;
        renderPage();
    }
}

// 페이지 처음 렌더링
document.addEventListener("DOMContentLoaded", renderPage);
