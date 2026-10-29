from app import app, db, Actividad
from sqlalchemy import text

def migrate():
    with app.app_context():
        # Agregar las nuevas columnas si no existen
        try:
            db.session.execute(text("ALTER TABLE ctl_actividades ADD COLUMN dias INTEGER DEFAULT 0"))
            print("Columna 'dias' agregada exitosamente")
        except Exception as e:
            print(f"Columna 'dias' ya existe o error: {e}")

        try:
            db.session.execute(text("ALTER TABLE ctl_actividades ADD COLUMN horas INTEGER DEFAULT 0"))
            print("Columna 'horas' agregada exitosamente")
        except Exception as e:
            print(f"Columna 'horas' ya existe o error: {e}")

        try:
            db.session.execute(text("ALTER TABLE ctl_actividades ADD COLUMN minutos INTEGER DEFAULT 0"))
            print("Columna 'minutos' agregada exitosamente")
        except Exception as e:
            print(f"Columna 'minutos' ya existe o error: {e}")

        db.session.commit()

        # Actualizar los registros existentes
        actividades = Actividad.query.all()
        for actividad in actividades:
            if actividad.dias == 0 and actividad.horas == 0 and actividad.minutos == 0:
                dias = actividad.tiempo // 540
                minutos_restantes = actividad.tiempo % 540
                horas = minutos_restantes // 60
                minutos = minutos_restantes % 60

                actividad.dias = dias
                actividad.horas = horas
                actividad.minutos = minutos

        db.session.commit()
        print(f"Se actualizaron {len(actividades)} registros existentes")
        print("Migración completada exitosamente")

if __name__ == '__main__':
    migrate()
