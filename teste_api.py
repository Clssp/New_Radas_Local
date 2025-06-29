# teste_api.py
import googlemaps
import os

# --- SUBSTITUA PELA SUA CHAVE DE API DO GOOGLE MAPS ---
# Copie e cole a mesma chave que está no seu secrets.toml
# Exemplo: API_KEY = "AIzaSy..."
API_KEY = "AIzaSyB832XdCTbKkpKOJP2P5XMnibhMxMgMJKE" 
# ----------------------------------------------------

print("Tentando inicializar o cliente do Google Maps...")

try:
    # Inicializa o cliente com a chave
    gmaps = googlemaps.Client(key=API_KEY)

    # Localização de teste
    localizacao_teste = "Morumbi, São Paulo"
    print(f"\nTentando geocodificar a localização: '{localizacao_teste}'")

    # Faz a chamada para a API de Geocodificação
    geocode_result = gmaps.geocode(localizacao_teste)

    # Verifica e imprime o resultado
    if geocode_result:
        print("\n--- SUCESSO! ---")
        print("A chamada para a API de Geocodificação funcionou.")
        primeiro_resultado = geocode_result[0]
        print(f"Endereço formatado: {primeiro_resultado.get('formatted_address')}")
        print(f"Coordenadas: {primeiro_resultado.get('geometry', {}).get('location')}")
    else:
        print("\n--- FALHA ---")
        print("A chamada foi feita, mas não retornou resultados. Isso pode ser normal para uma localização inválida.")

except googlemaps.exceptions.ApiError as e:
    print("\n--- ERRO DE API! ---")
    print(f"A API retornou um erro: {e}")
    print("\nPossíveis causas:")
    print("1. A chave de API é inválida.")
    print("2. A API 'Geocoding API' não está ativada no seu projeto do Google Cloud.")
    print("3. Sua conta de faturamento no Google Cloud tem algum problema.")
    print("4. A chave de API tem restrições (ex: de IP ou de HTTP referrer) que estão bloqueando a requisição.")

except Exception as e:
    print(f"\n--- ERRO INESPERADO! ---")
    print(f"Ocorreu um erro diferente: {e}")