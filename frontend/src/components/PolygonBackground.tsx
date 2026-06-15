export default function PolygonBackground() {
  return (
    <div
      className="fixed inset-0 z-0 pointer-events-none bg-cover bg-center bg-no-repeat bg-fixed"
      style={{ backgroundImage: "url('/adwaita-day.png')" }}
    />
  );
}
