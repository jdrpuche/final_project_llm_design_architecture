const formulario = document.getElementById("formulario");
const input = document.getElementById("pregunta");
const historial = document.getElementById("historial");

function agregarMensaje(rol, texto) {
  const burbuja = document.createElement("div");
  burbuja.className = `mensaje ${rol}`;
  burbuja.textContent = texto;
  historial.appendChild(burbuja);
  historial.scrollTop = historial.scrollHeight;
  return burbuja;
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const pregunta = input.value.trim();
  if (!pregunta) return;

  agregarMensaje("usuario", pregunta);
  input.value = "";
  const cargando = agregarMensaje("cargando", "Consultando fuentes autorizadas...");

  try {
    const respuesta = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta }),
    });
    const datos = await respuesta.json();
    historial.removeChild(cargando);

    if (datos.ok) {
      agregarMensaje("agente", datos.respuesta);
    } else {
      const texto = datos.detalle ? `${datos.error}\n\nDetalle: ${datos.detalle}` : datos.error;
      agregarMensaje("error", texto);
    }
  } catch (error) {
    historial.removeChild(cargando);
    agregarMensaje("error", "No fue posible conectar con el servidor. Revisa que el backend esté corriendo.");
  }
});
