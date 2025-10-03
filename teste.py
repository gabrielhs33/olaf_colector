from Olaf import Olaf, OlafCommand

ref = "teste audios/PASSO BEM SOLTO (Slowed).mp3"
outro = "teste audios/speed.mp3"

print("referencia")
Olaf(OlafCommand.STORE, ref).do()

print("olhando outro")
achou = Olaf(OlafCommand.QUERY, outro).do()
print(achou)
