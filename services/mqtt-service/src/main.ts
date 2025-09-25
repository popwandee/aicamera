import { NestFactory } from '@nestjs/core';
import { MicroserviceOptions, Transport } from '@nestjs/microservices';
import { ValidationPipe } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { Logger } from '@aicamera/shared';
import { ConfigService } from '@nestjs/config';

async function bootstrap() {
  const logger = Logger.create('MQTT-Service');

  // Create HTTP application for REST API
  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);

  const port = configService.get('PORT', 3001);
  const nodeEnv = configService.get('NODE_ENV', 'development');

  // Global validation pipe
  app.useGlobalPipes(new ValidationPipe({
    transform: true,
    whitelist: true,
    forbidNonWhitelisted: true,
  }));

  // CORS configuration
  app.enableCors({
    origin: configService.get('CORS_ORIGINS', 'http://localhost:8080').split(','),
    credentials: true,
  });

  // Swagger documentation
  if (nodeEnv !== 'production') {
    const config = new DocumentBuilder()
      .setTitle('AI Camera MQTT Service')
      .setDescription('MQTT Microservice for edge device communication')
      .setVersion('1.0')
      .addBearerAuth()
      .build();
    
    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('docs', app, document);
  }

  // Connect microservice for MQTT communication
  const mqttUrl = configService.get('MQTT_URL', 'mqtt://localhost:1883');
  app.connectMicroservice<MicroserviceOptions>({
    transport: Transport.MQTT,
    options: {
      url: mqttUrl,
      clientId: `mqtt-service-${Date.now()}`,
      clean: true,
      keepalive: 60,
      reconnectPeriod: 1000,
      connectTimeout: 30 * 1000,
    },
  });

  // Start all services
  await app.startAllMicroservices();
  await app.listen(port);

  logger.info(`MQTT Service started on port ${port}`);
  logger.info(`Environment: ${nodeEnv}`);
  logger.info(`MQTT Broker: ${mqttUrl}`);
  logger.info(`Documentation: http://localhost:${port}/docs`);
}

bootstrap().catch((error) => {
  const logger = Logger.create('MQTT-Service');
  logger.error('Failed to start MQTT service', error);
  process.exit(1);
});