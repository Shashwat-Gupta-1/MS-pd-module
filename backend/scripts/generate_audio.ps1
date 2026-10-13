Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("uploads/recordings/test_interview.wav")
$synth.Speak("What is your monthly business turnover? My monthly sales is around 2 lakh rupees. How much is the shop rent? The shop rent is 8000 rupees per month.")
$synth.Dispose()
Write-Host "Sample audio generated at uploads/recordings/test_interview.wav"
