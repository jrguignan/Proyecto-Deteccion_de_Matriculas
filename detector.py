from ultralytics import YOLO
import pytesseract
import cv2
import supervision as sv
from supervision.draw.color import ColorPalette
from supervision.detection.annotate import BoxAnnotator
import numpy as np

# funcion que recorta imagenes
def cropped(detections,image):
    bounding_box = detections.xyxy
    # Extraer las coordenadas de la caja delimitadora
    xmin, ymin, xmax, ymax = bounding_box[0]
    # Asegurarse de que las coordenadas sean enteros
    xmin, ymin, xmax, ymax = int(xmin), int(ymin), int(xmax), int(ymax)
    # Recortar la imagen usando las coordenadas de la caja delimitadora
    cropped_image = image[ymin:ymax, xmin:xmax]
    return cropped_image


def main():
    #Directorio donde esta el video a analizar
    cap = cv2.VideoCapture('videos/video.mp4')
    # Verificar si el video se abrió correctamente
    if not cap.isOpened():
       print("Error: No se puede abrir el archivo de video")
       exit()

    #Para inicializar el conteo de frame
    frame_number = 0

    #Permite sacar informacion del video analizado para usarlo en el de salida
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    #Configuracion de formato del video de salida
    output_video_path = 'videooutput_video.mp4'  # Ruta del archivo de salida
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codificador para el archivo de salida
    out = cv2.VideoWriter('videos/output_video.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))


    while cap.isOpened():
        #Lee el video frame a frame
        ret,frame = cap.read()
        #Suma 1 al conteo de frame
        frame_number +=1 
        #Para salir del bucle while
        if not ret:
           break 

        #modelo para detectar el medio de transporte
        model_t = YOLO('models\yolov10n.pt')
        #Imprime el numero de frame que se está analizando
        print("Numero de frame: ",frame_number)

        #se pasa la imagen por el modelo que detecta el medio de transporte
        results_t = model_t(frame)[0]
        #se pasan los resultados a la libreria supervison
        detections_t = sv.Detections.from_ultralytics(results_t)

        # class_ids of interest - car, motorcycle, bus and truck
        class_id = [2, 3, 5, 7]

        #filtra que solo muestre las detecciones de class_id
        if detections_t.class_id[0] in class_id:
            #inicializa las etiquetas
            bounding_box_annotator = sv.BoundingBoxAnnotator()
            label_annotator = sv.LabelAnnotator()
            #Se pasa la informacion que se mostrara en las etiqutes
            annotated_image_t = bounding_box_annotator.annotate(scene=frame, detections=detections_t)
            annotated_image_t = label_annotator.annotate(scene=annotated_image_t, detections=detections_t)

            #recorte de imagen de  medio de transporte
            cropped_image_t = cropped(detections_t, frame)
            
            #modelo para detectar el medio de matricula
            model_p = YOLO('models\placa.pt')
            #se pasa la imagen por el modelo que detecta matriculas
            #Se hace con la imagen recortada para mejorar la deteccion
            results_p = model_p(cropped_image_t, agnostic_nms = True)[0]
            #modifica a matricula el nombre que trae por defecto el modelo
            results_p.names[0] = "Matricula"
            #se pasan los resultados a la libreria supervison
            detections_p = sv.Detections.from_ultralytics(results_p)

            #Saca la imagen de la matricula antes de cambiar 
            cropped_image_matricula = cropped(detections_p, cropped_image_t)


            #PARA PODER PASAR LA COORDENADAS DE LA MATRICULA EN LA IMAGEN CORTADA A LA IMAGEN 
            #MAS GRANDE 
            #diferencia de las coordenadas XY, el largo y ancho de la caja de la matricula
            dif_x = results_p.boxes.xyxy[0][2] - results_p.boxes.xyxy[0][0]
            dif_y = results_p.boxes.xyxy[0][3] - results_p.boxes.xyxy[0][1]
            #Puntos iniciales, suma del punto de deteccion de la placa mas el del medio de transporte
            x1_nuevo = detections_t.xyxy[0][0] + detections_p.xyxy[0][0]
            y1_nuevo = detections_t.xyxy[0][1] + detections_p.xyxy[0][1] 
            #puntos dinales, suma del pueto inicial mas las dimensiones de la box de matricula
            x2_nuevo = x1_nuevo + dif_x  
            y2_nuevo = y1_nuevo + dif_y 
            #salvar las nuevas coordenadas 
            detections_p.xyxy = np.array([[x1_nuevo,y1_nuevo,x2_nuevo,y2_nuevo]])


            #inicializa las etiquetas de matriculas
            bounding_box_annotator = sv.BoundingBoxAnnotator()
            label_annotator = sv.LabelAnnotator()
            #Se pasa la informacion que se mostrara en las etiqutes
            annotated_image_p = bounding_box_annotator.annotate(scene=frame, detections=detections_p)
            annotated_image_p = label_annotator.annotate(scene=annotated_image_p, detections=detections_p)
            #transforma el formato de color al formato comun
        
            #lectura de la placa con tesseract OCR

            #TRANSFORMACIONES DE LA IMAGEN PARA MEJORAR LA LECTURA  DEL OCR
            # Cargamos la imagen, y la convertimos a escala de grises.
            gray = cv2.cvtColor(cropped_image_matricula, cv2.COLOR_BGR2GRAY)


            #Cambiar directorio donde esta instalado tesseract
            pytesseract.pytesseract.tesseract_cmd = r'C:/Program Files/Tesseract-OCR/tesseract.exe'

            #Pasa el OCR por la imagen en escala de grises y filtra solo numero y letras
            data = pytesseract.image_to_string(gray, lang='eng', config='--psm 10 --oem 3 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYXabcdefghijklmnopqrstuvwxyz')

            #Limpieza de la cadena de salida del OCR
            valor_medio = round(len(data)/2)
            data = data[valor_medio-3:valor_medio+4]
            
          
            #PARA AGREGAR LA MATRICULA EN LA IMAGEN
            #Definir el texto a añadir
            text = data
            #Definir la posición del texto
            position = (900, 60)  # Puedes ajustar la posición según necesites
            #Definir la fuente, tamaño, color, grosor
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 2
            font_color = (255, 255, 255)  # Blanco en BGR
            font_thickness = 6
            #Añadir el texto a la imagen
            frame = cv2.putText(annotated_image_p, text, position, font, font_scale, font_color, font_thickness)
            print(text)

            #Guarda el frame para construir el video
            out.write(frame)
            
            #Muestra el frame mientra se guardan para el video
            #cv2.imshow('Frame', frame)
            #if cv2.waitKey(1) & 0xFF == ord('q'):
            #   break

        

    cap.release()
    out.release()

   
if __name__ == "__main__":
    main()