from main import create_app
from models import db, Company
from config import config


def init_database():
    """Initialize database with default data"""
    app = create_app('development')

    with app.app_context():
        # Create all tables
        db.create_all()

        # Check if companies already exist
        if Company.query.count() == 0:
            companies = [
                {"name": "EcoEnergy Plus", "symbol": "EEP", "category": "Energia renovable", "base_price": 25.50,
                 "description": "Lider en energia solar y eolica", "icon": "fa-leaf"},
                {"name": "TechFuture AI", "symbol": "TFAI", "category": "Inteligencia artificial", "base_price": 120.75,
                 "description": "Desarrollo de IA de vanguardia", "icon": "fa-microchip"},
                {"name": "SpaceX Ventures", "symbol": "SPXV", "category": "Aeroespacial", "base_price": 350.20,
                 "description": "Exploracion espacial comercial", "icon": "fa-rocket"},
                {"name": "BioMed Solutions", "symbol": "BMS", "category": "Biotecnologia", "base_price": 85.40,
                 "description": "Investigacion medica avanzada", "icon": "fa-dna"},
                {"name": "GreenTransport", "symbol": "GRT", "category": "Transporte", "base_price": 42.30,
                 "description": "Vehiculos electricos sostenibles", "icon": "fa-car"},
                {"name": "CloudNet Systems", "symbol": "CNS", "category": "Tecnologia", "base_price": 65.80,
                 "description": "Soluciones de computacion en la nube", "icon": "fa-cloud"},
                {"name": "FoodTech Innovations", "symbol": "FTI", "category": "Alimentos", "base_price": 38.90,
                 "description": "Tecnologia alimentaria sostenible", "icon": "fa-utensils"},
                {"name": "RoboTech Industries", "symbol": "RTI", "category": "Robotica", "base_price": 95.60,
                 "description": "Automatizacion industrial avanzada", "icon": "fa-robot"},
                {"name": "WaterPure Solutions", "symbol": "WPS", "category": "Medio ambiente", "base_price": 22.75,
                 "description": "Tecnologias de purificacion de agua", "icon": "fa-tint"},
                {"name": "Quantum Computing", "symbol": "QCC", "category": "Tecnologia", "base_price": 180.50,
                 "description": "Computacion cuantica de proxima generacion", "icon": "fa-atom"},
                {"name": "EcoFashion", "symbol": "EFN", "category": "Moda", "base_price": 31.20,
                 "description": "Ropa sostenible y etica", "icon": "fa-tshirt"},
                {"name": "SmartHome Tech", "symbol": "SHT", "category": "Tecnologia", "base_price": 55.40,
                 "description": "Sistemas de hogar inteligente", "icon": "fa-home"},
                {"name": "Virtual Reality Co", "symbol": "VRC", "category": "Entretenimiento", "base_price": 78.90,
                 "description": "Experiencias de realidad virtual inmersivas", "icon": "fa-vr-cardboard"},
                {"name": "BioFuels Global", "symbol": "BFG", "category": "Energia", "base_price": 19.85,
                 "description": "Produccion de biocombustibles sostenibles", "icon": "fa-gas-pump"},
                {"name": "HealthTech Plus", "symbol": "HTP", "category": "Salud", "base_price": 62.30,
                 "description": "Tecnologias para el cuidado de la salud", "icon": "fa-heartbeat"},
                {"name": "CryptoVault", "symbol": "CRV", "category": "Finanzas", "base_price": 145.70,
                 "description": "Seguridad de activos digitales", "icon": "fa-lock"},
                {"name": "Urban Farming", "symbol": "URF", "category": "Agricultura", "base_price": 27.60,
                 "description": "Soluciones de agricultura urbana", "icon": "fa-seedling"},
                {"name": "NanoTech Materials", "symbol": "NTM", "category": "Materiales", "base_price": 92.40,
                 "description": "Materiales avanzados a nanoescala", "icon": "fa-atom"},
                {"name": "EduTech Global", "symbol": "EDG", "category": "Educacion", "base_price": 41.80,
                 "description": "Plataformas de aprendizaje digital", "icon": "fa-graduation-cap"},
                {"name": "AutoDrive Systems", "symbol": "ADS", "category": "Automocion", "base_price": 125.30,
                 "description": "Tecnologia de conduccion autonoma", "icon": "fa-car-side"},
                {"name": "Renewable Storage", "symbol": "RES", "category": "Energia", "base_price": 53.70,
                 "description": "Soluciones de almacenamiento de energia", "icon": "fa-battery-full"},
                {"name": "Ocean Cleanup", "symbol": "OCC", "category": "Medio ambiente", "base_price": 18.90,
                 "description": "Tecnologias de limpieza oceanica", "icon": "fa-water"},
                {"name": "Digital Security", "symbol": "DSC", "category": "Ciberseguridad", "base_price": 88.60,
                 "description": "Proteccion de datos y sistemas", "icon": "fa-shield-alt"},
                {"name": "Space Tourism", "symbol": "SPT", "category": "Turismo", "base_price": 215.40,
                 "description": "Experiencias turisticas espaciales", "icon": "fa-space-shuttle"},
                {"name": "AI Healthcare", "symbol": "AIH", "category": "Salud", "base_price": 105.80,
                 "description": "Diagnostico medico con IA", "icon": "fa-user-md"}
            ]

            for company_data in companies:
                company = Company(**company_data)
                db.session.add(company)

            db.session.commit()
            print("✅ Database initialized with companies")
        else:
            print("✅ Database already contains data")


if __name__ == '__main__':
    init_database()