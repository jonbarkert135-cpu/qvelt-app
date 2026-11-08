const en = {
  skip: "Skip to content", workspace: "Workspace", newChat: "New chat",
  conversations: "Conversations", history: "Your conversations will appear here.",
  projects: "Projects", soon: "Coming soon", navigation: "Navigation",
  openNavigation: "Open navigation", closeNavigation: "Close navigation",
  collapse: "Collapse sidebar", expand: "Expand sidebar", language: "Language",
  appearance: "Appearance", system: "System", light: "Light", dark: "Dark",
  eyebrow: "A SPACE TO THINK", heading: "Where shall we begin?",
  intro: "Bring a question, an unfinished idea, or a fresh perspective.",
  concept: "Explain a concept", conceptPrompt: "Help me understand a concept step by step.",
  idea: "Shape an idea", ideaPrompt: "Help me turn an idea into a clear plan.",
  code: "Think through code", codePrompt: "Help me think through a programming problem.",
  message: "Your message", placeholder: "What's on your mind?", send: "Send message",
  unavailable: "Messaging is coming soon. Your draft stays in this tab.",
  discard: "Discard this draft and start a new chat?", footer: "A little clarity goes a long way.",
};

export type Messages = { [K in keyof typeof en]: string };
export const locales = ["en", "uk", "ru"] as const;
export type Locale = typeof locales[number];
export const themes = ["system", "light", "dark"] as const;
export type Theme = typeof themes[number];

export const messages: Record<Locale, Messages> = {
  en,
  uk: {
    skip: "Перейти до вмісту", workspace: "Робочий простір", newChat: "Новий чат",
    conversations: "Розмови", history: "Тут з’являться ваші розмови.",
    projects: "Проєкти", soon: "Незабаром", navigation: "Навігація",
    openNavigation: "Відкрити навігацію", closeNavigation: "Закрити навігацію",
    collapse: "Згорнути бічну панель", expand: "Розгорнути бічну панель", language: "Мова",
    appearance: "Вигляд", system: "Як у системі", light: "Світлий", dark: "Темний",
    eyebrow: "ПРОСТІР ДЛЯ ДУМОК", heading: "З чого почнемо?",
    intro: "Приходьте із запитанням, незавершеною ідеєю чи свіжим поглядом.",
    concept: "Розібратися в понятті", conceptPrompt: "Допоможи мені зрозуміти поняття крок за кроком.",
    idea: "Розвинути ідею", ideaPrompt: "Допоможи перетворити ідею на чіткий план.",
    code: "Обміркувати код", codePrompt: "Допоможи розібратися із завданням з програмування.",
    message: "Ваше повідомлення", placeholder: "Про що ви думаєте?", send: "Надіслати повідомлення",
    unavailable: "Обмін повідомленнями з’явиться незабаром. Чернетка залишається в цій вкладці.",
    discard: "Відкинути цю чернетку та почати новий чат?", footer: "Трохи ясності — і рухатися легше.",
  },
  ru: {
    skip: "Перейти к содержимому", workspace: "Рабочее пространство", newChat: "Новый чат",
    conversations: "Разговоры", history: "Здесь появятся ваши разговоры.",
    projects: "Проекты", soon: "Скоро", navigation: "Навигация",
    openNavigation: "Открыть навигацию", closeNavigation: "Закрыть навигацию",
    collapse: "Свернуть боковую панель", expand: "Развернуть боковую панель", language: "Язык",
    appearance: "Оформление", system: "Как в системе", light: "Светлое", dark: "Тёмное",
    eyebrow: "ПРОСТРАНСТВО ДЛЯ МЫСЛЕЙ", heading: "С чего начнём?",
    intro: "Приходите с вопросом, незаконченной идеей или свежим взглядом.",
    concept: "Разобраться в понятии", conceptPrompt: "Помоги мне понять понятие шаг за шагом.",
    idea: "Развить идею", ideaPrompt: "Помоги превратить идею в чёткий план.",
    code: "Обдумать код", codePrompt: "Помоги разобраться с задачей по программированию.",
    message: "Ваше сообщение", placeholder: "О чём вы думаете?", send: "Отправить сообщение",
    unavailable: "Обмен сообщениями появится скоро. Черновик остаётся в этой вкладке.",
    discard: "Удалить этот черновик и начать новый чат?", footer: "Немного ясности — и двигаться легче.",
  },
};
