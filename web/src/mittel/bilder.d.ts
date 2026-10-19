/* Vite liefert Bildimporte als URL zurück. Ohne diese Angabe kennt
   TypeScript den Typ nicht — `vite/client` deckt es zwar ab, hier steht es
   noch einmal, damit der Bau auch ohne diese Typen durchläuft. */
declare module "*.png" {
  const pfad: string;
  export default pfad;
}

declare module "*.webp" {
  const pfad: string;
  export default pfad;
}
