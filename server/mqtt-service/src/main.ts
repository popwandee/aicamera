import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { MicroserviceOptions, Transport } from '@nestjs/microservices';

async function bootstrap() {
  const microservice =
    await NestFactory.createMicroservice<MicroserviceOptions>(AppModule, {
      transport: Transport.MQTT,
      options: {
        url: process.env.MQTT_URL ?? 'mqtt://broker:1883',
      },
    });

  await microservice.listen();
}

void bootstrap();
