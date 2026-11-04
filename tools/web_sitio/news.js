// Añade las noticias aquí, en inglés y en español (la web es bilingüe: i18n.js). Fecha ISO: AAAA-MM-DD; la más reciente
// aparece primero. Cada entrada: date, category, title, summary, paragraphs (lista) y "es" con los mismos campos en español.
// Si falta "es", en español se ve la versión en inglés.
window.SERVER_NEWS = [
  {
    date: "2026-10-31",
    category: "What's new",
    title: "New launcher and accounts from the website",
    summary: "You can now download our launcher: it keeps the game up to date on its own and starts it in one click. Accounts are now created on this page.",
    paragraphs: [
      "The launcher downloads the full patch and checks that it arrives without errors, so you no longer need to reinstall the client for every update. Copy it into the game folder, next to angel.dat.",
      "New accounts are created in the \"Create your account\" section, with your username and password: they're the same ones you use to log in to the game."
    ],
    es: {
      category: "Novedades",
      title: "Nuevo launcher y cuentas desde la web",
      summary: "Ya puedes descargar nuestro launcher: mantiene el juego al día solo y lo abre con un clic. Las cuentas se crean ahora en esta página.",
      paragraphs: [
        "El launcher descarga el parche completo y verifica que llegue sin errores, así que ya no hace falta volver a instalar el cliente en cada actualización. Cópialo dentro de la carpeta del juego, junto a angel.dat.",
        "Las cuentas nuevas se crean en la sección «Crea tu cuenta», con tu usuario y tu contraseña: son los mismos con los que entras al juego."
      ]
    }
  },
  {
    date: "2026-10-30",
    category: "Dungeons",
    title: "Dark Cavern opens its doors",
    summary: "A lava cave for levels 45 to 60, with Dragonkin Moowad waiting at the bottom.",
    paragraphs: [
      "Each party enters its own copy of the cave. Defeating the boss opens an exit portal just for your party."
    ],
    es: {
      category: "Mazmorras",
      title: "Dark Cavern abre sus puertas",
      summary: "Una cueva de lava para niveles 45 a 60, con el Dragonkin Moowad esperando al fondo.",
      paragraphs: [
        "Cada equipo entra en su propia copia de la cueva. Al vencer al jefe aparece un portal de salida solo para tu equipo."
      ]
    }
  },
  {
    date: "2026-10-30",
    category: "Community",
    title: "Introducing the news board",
    summary: "The website now has a place that gathers the server's updates and announcements.",
    paragraphs: [
      "This is where the team will post news, patch notes and maintenance notices."
    ],
    es: {
      category: "Comunidad",
      title: "Estrenamos el tablón de noticias",
      summary: "La web ya cuenta con un espacio para reunir las actualizaciones y los anuncios del servidor.",
      paragraphs: [
        "En esta sección publicaremos las novedades, notas de actualización y avisos de mantenimiento del equipo."
      ]
    }
  }
];
