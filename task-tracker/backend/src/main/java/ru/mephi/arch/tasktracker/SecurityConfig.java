package ru.mephi.arch.tasktracker;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtDecoders;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {
    @Bean SecurityFilterChain security(HttpSecurity http) throws Exception {
        return http.csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(auth -> auth.requestMatchers("/actuator/health/**").permitAll().anyRequest().authenticated())
            .exceptionHandling(ex -> ex
                .authenticationEntryPoint((request,response,error) -> securityError(response,401,"token","unauthorized"))
                .accessDeniedHandler((request,response,error) -> securityError(response,403,"permission","forbidden")))
            .oauth2ResourceServer(oauth -> oauth.jwt(Customizer.withDefaults())).build();
    }
    private static void securityError(jakarta.servlet.http.HttpServletResponse response,int status,String field,String reason) throws java.io.IOException {
        response.setStatus(status);response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"correlationId\":\""+ApiAdvice.correlationId()+"\",\"errors\":[{\"field\":\""+field+"\",\"reason\":\""+reason+"\"}]}");
    }

    @Bean JwtDecoder jwtDecoder(@Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String issuer,
                               @Value("${app.audience}") String audience,
                               @Value("${app.jwks-uri:}") String jwksUri) {
        NimbusJwtDecoder decoder = jwksUri.isBlank() ? JwtDecoders.fromIssuerLocation(issuer) : NimbusJwtDecoder.withJwkSetUri(jwksUri).build();
        OAuth2TokenValidator<Jwt> validator = token -> {
            var issuerResult = JwtValidators.createDefaultWithIssuer(issuer).validate(token);
            if (issuerResult.hasErrors()) return issuerResult;
            return token.getAudience().contains(audience)
                ? OAuth2TokenValidatorResult.success()
                : OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token", "invalid_audience", null));
        };
        decoder.setJwtValidator(validator);
        return decoder;
    }
}
