let balanceUpdater; // Глобальная переменная для интервала обновления баланса

// Функция для показа выбранной секции
function showSection(sectionId) {
    // Скрываем все секции
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
        section.style.display = 'none'; // Скрываем каждую секцию
    });

    // Показываем выбранную секцию
    const section = document.getElementById(sectionId);
    section.classList.add('active');
    section.style.display = 'block'; // Показываем выбранную секцию

    // Если выбрана секция "Основная информация", обновляем баланс
    if (sectionId === 'info') {
        startBalanceUpdater(); // Запускаем обновление баланса
    } else {
        stopBalanceUpdater(); // Останавливаем обновление баланса, если ушли с вкладки
    }
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

// Функция для обновления баланса
async function fetchBalance() {
    const balanceText = document.getElementById("balance-text");
    const refreshButton = document.getElementById("refresh-balance-button");

    // Уведомляем пользователя, что баланс обновляется
    balanceText.innerText = "Обновляется...";
    refreshButton.disabled = true; // Делаем кнопку неактивной

    try {
        const response = await fetch("/get-balance");
        const data = await response.json();

        if (data.error) {
            balanceText.innerText = `Ошибка: ${data.error}`;
        } else {
            balanceText.innerText = `Ваш баланс: ${data.totalWalletBalance} USDT`;
        }
    } catch (error) {
        console.error("Ошибка при запросе баланса:", error);
        balanceText.innerText = "Ошибка загрузки баланса.";
    } finally {
        refreshButton.disabled = false; // Возвращаем активность кнопке
    }
}



// Запускаем обновление раз в минуту
function startBalanceUpdater() {
    fetchBalance(); // Обновляем сразу
    balanceUpdater = setInterval(fetchBalance, 60000); // Каждую минуту
}

// Останавливаем обновление
function stopBalanceUpdater() {
    clearInterval(balanceUpdater);
}

// Загружаем список API ключей
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
        apiKeyContainer.innerHTML = ""; // Очищаем контейнер перед загрузкой

        // Создаем элементы для каждого API ключа
        apiKeys.forEach(apiKey => {
            const keyElement = document.createElement("div");
            keyElement.classList.add("api-key-item");
            keyElement.innerHTML = `
                <p><strong>Биржа:</strong> ${apiKey.exchange}</p>
                <p><strong>API ключ:</strong> ${apiKey.api_key}</p>
                <p><strong>Дата создания:</strong> ${new Date(apiKey.created_at).toLocaleDateString()}</p>
                <button onclick="deleteApiKey(${apiKey.id})">Удалить</button>
            `;
            apiKeyContainer.appendChild(keyElement);
        });

    } catch (error) {
        console.error("Ошибка при загрузке API ключей:", error);
    }
}


// Запускаем загрузку API ключей и баланс при загрузке страницы
document.addEventListener("DOMContentLoaded", () => {
    loadApiKeys();
    showSection('info'); // Устанавливаем вкладку "Основная информация" по умолчанию
});

// Функция для сохранения API ключей
async function saveApiKey() {
    console.log("Функция saveApiKey вызвана");
    // Получаем данные из полей модального окна
    const exchange = document.getElementById("exchange-select").value;
    const apiKey = document.getElementById("api-key").value;
    const secretKey = document.getElementById("secret-key").value;
    console.log(exchange);

    // Проверяем, что все поля заполнены
    if (!exchange || !apiKey || !secretKey) {
        alert("Пожалуйста, заполните все поля.");
        return;
    }

    try {
        // Отправляем данные на сервер
        const response = await fetch("/api-keys", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                exchange: exchange,
                api_key: apiKey,
                secret_key: secretKey,
            }),
        });

        if (!response.ok) {
            throw new Error("Ошибка при сохранении API ключа");
        }

        alert("API ключ успешно сохранён!");
        closeModal(); // Закрываем модальное окно
        loadApiKeys(); // Обновляем список API ключей на странице
    } catch (error) {
        console.error("Ошибка при сохранении API ключа:", error);
        alert("Произошла ошибка при сохранении API ключа. Попробуйте снова.");
    }
}


async function deleteApiKey(apiKeyId) {
    const confirmDelete = confirm("Вы уверены, что хотите удалить этот API ключ?");
    if (!confirmDelete) {
        return;
    }

    try {
        const response = await fetch(`/api-keys/${apiKeyId}`, {
            method: "DELETE",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Ошибка при удалении API ключа");
        }

        alert("API ключ успешно удалён!");
        loadApiKeys(); // Перезагружаем список API ключей
    } catch (error) {
        console.error("Ошибка при удалении API ключа:", error);
        alert("Произошла ошибка при удалении API ключа. Попробуйте снова.");
    }
}


// Загрузка списка ботов пользователя
async function loadUserBots() {
    try {
        const response = await fetch("/user-bots");
        const text = await response.text(); // Получаем текст ответа
        console.log("Ответ сервера:", text);

        const bots = JSON.parse(text); // Парсим JSON, если это возможно
        console.log("Данные ботов:", bots);

        const botList = document.getElementById("bot-list");
        botList.innerHTML = ""; // Очистка списка

        bots.forEach(bot => {
            const listItem = document.createElement("li");
            listItem.innerHTML = `
                <h4>${bot.name}</h4>
                <p>Стратегия: ${bot.strategy}</p>
                <p>Статус: ${bot.status}</p>
                <div class="bot-controls">
                    <button onclick="startBot(${bot.id}, '${bot.name}', '${bot.strategy}')">Запустить</button>
                    <button onclick="stopBot(${bot.id})">Остановить</button>
                    <button onclick="showBotInfo(${bot.id})">Информация</button>
                    <button onclick="editBotConfig(${bot.id})">Изменить конфигурацию</button>
                </div>
            `;
            botList.appendChild(listItem);
        });
    } catch (error) {
        console.error("Ошибка при загрузке ботов:", error);
    }
}


// Функции для управления ботами
async function startBot(botId, botName, strategyName) {
    try {
        const response = await fetch(`/start-bot/${botName}/${strategyName}`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${localStorage.getItem("access_token")}`
            }
        });

        const result = await response.json();
        alert(result.message);
        loadUserBots(); // Обновляем список ботов
    } catch (error) {
        console.error("Ошибка при запуске бота:", error);
    }
}



async function stopBot(botId) {
    try {
        await fetch(`/stop-bot/${botId}`, { method: "POST" });
        alert("Бот остановлен!");
        loadUserBots(); // Обновление списка
    } catch (error) {
        console.error("Ошибка при остановке бота:", error);
    }
}

async function showBotInfo(botId) {
    alert(`Информация о боте с ID: ${botId}`);
    // Здесь можно добавить отображение полной информации о боте
}

async function editBotConfig(botId) {
    alert(`Изменение конфигурации бота с ID: ${botId}`);
    // Здесь можно реализовать функциональность редактирования конфигурации
}

// Загружаем список ботов при загрузке страницы
document.addEventListener("DOMContentLoaded", loadUserBots);
