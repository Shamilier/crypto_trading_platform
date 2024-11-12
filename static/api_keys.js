// Функция для показа выбранной секции
function showSection(sectionId) {
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });
    document.getElementById(sectionId).classList.add('active');
}

// Функция для открытия модального окна
function openModal() {
    document.getElementById("apiModal").style.display = "block";
}

// Функция для закрытия модального окна
function closeModal() {
    document.getElementById("apiModal").style.display = "none";
}

// Функция для отображения полей API ключей после выбора биржи
function showApiFields() {
    document.getElementById("api-fields").style.display = "block";
}

// Функция для показа уведомления об успешном сохранении
function showSuccessMessage(message) {
    const successMessage = document.getElementById("successMessage");
    successMessage.textContent = message;
    successMessage.classList.add("visible");

    // Убираем уведомление через 2 секунды
    setTimeout(() => {
        successMessage.classList.remove("visible");
    }, 2000);
}

// Функция для сохранения API ключа
// Функция для отправки нового API ключа на сервер
async function saveApiKey() {
    // Получаем данные из формы
    const exchange = document.getElementById("exchange-select").value;
    const apiKey = document.getElementById("api-key").value;
    const secretKey = document.getElementById("secret-key").value;

    // Проверяем, что все поля заполнены
    if (!exchange || !apiKey || !secretKey) {
        alert("Пожалуйста, заполните все поля.");
        return;
    }

    try {
        // Отправляем POST-запрос на сервер для сохранения API ключей
        const response = await fetch("/api-keys", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ exchange, api_key: apiKey, secret_key: secretKey })
        });

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.detail || "Ошибка при добавлении API ключа");
        }

        // Обновляем список ключей после добавления
        await loadApiKeys();

        // Закрываем модальное окно и очищаем поля
        closeModal();
        document.getElementById("exchange-select").value = "";
        document.getElementById("api-key").value = "";
        document.getElementById("secret-key").value = "";

    } catch (error) {
        console.error("Ошибка при добавлении API ключа:", error);
        alert("Произошла ошибка. Попробуйте снова.");
    }
}


// Закрытие модального окна при клике на затемненный фон
window.onclick = function(event) {
    const modal = document.getElementById("apiModal");
    if (event.target === modal) {
        closeModal();
    }
}


async function loadApiKeys() {
    try {
        const response = await fetch("/api-keys", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error("Ошибка при загрузке API ключей");
        }

        const apiKeys = await response.json();
        
        const apiKeyContainer = document.getElementById("apiKeyContainer");
        apiKeyContainer.innerHTML = "";  // Очищаем контейнер перед загрузкой

        // Проходим по списку API ключей и создаем элементы для их отображения
        apiKeys.forEach(apiKey => {
            const keyElement = document.createElement("div");
            keyElement.classList.add("api-key-item");
            keyElement.innerHTML = `
                <p><strong>Биржа:</strong> ${apiKey.exchange}</p>
                <p><strong>API ключ:</strong> ${apiKey.api_key}</p>
                <p><strong>Дата создания:</strong> ${new Date(apiKey.created_at).toLocaleDateString()}</p>
            `;
            apiKeyContainer.appendChild(keyElement);
        });

    } catch (error) {
        console.error("Ошибка при загрузке API ключей:", error);
    }
}

// Вызываем загрузку API ключей при открытии страницы
document.addEventListener("DOMContentLoaded", loadApiKeys);


document.addEventListener("DOMContentLoaded", () => {
    loadApiKeys();
});
